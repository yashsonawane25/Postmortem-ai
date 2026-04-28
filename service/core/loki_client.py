"""
Loki client for PostmortemAI.
Fetches recent logs for a pod and classifies error/warning lines.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from core.models import LokiData

logger = logging.getLogger(__name__)

# Patterns used to classify log lines
_ERROR_RE = re.compile(r"\b(ERROR|FATAL|EXCEPTION|CRITICAL|panic|OOMKilled)\b", re.IGNORECASE)
_WARN_RE = re.compile(r"\b(WARN|WARNING|DEPRECATED)\b", re.IGNORECASE)


class LokiClient:
    def __init__(self, base_url: str, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ── Low-level query ──────────────────────────────────────────────────────

    async def _query_range(
        self,
        logql: str,
        start_ns: int,
        end_ns: int,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Execute a Loki range query and return the stream results."""
        url = f"{self.base_url}/loki/api/v1/query_range"
        params = {
            "query": logql,
            "start": str(start_ns),
            "end": str(end_ns),
            "limit": str(limit),
            "direction": "backward",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                body = resp.json()

            if body.get("status") != "success":
                logger.warning("Loki query returned non-success: %s", body)
                return []

            return body.get("data", {}).get("result", [])

        except httpx.HTTPError as exc:
            logger.error("Loki HTTP error: %s", exc)
            return []

    # ── Public method ────────────────────────────────────────────────────────

    async def collect(
        self,
        namespace: str,
        pod: str,
        lookback_minutes: int = 30,
        limit: int = 200,
    ) -> LokiData:
        """
        Fetch logs for a pod from the last `lookback_minutes` minutes.
        Splits lines into all / error / warn buckets.
        """
        now_ns = int(datetime.now(timezone.utc).timestamp() * 1e9)
        start_ns = now_ns - lookback_minutes * 60 * int(1e9)

        # Loki label selectors — works with the default promtail config
        # that ships with loki-stack Helm chart
        logql = (
            f'{{namespace="{namespace}", pod=~"{pod}.*"}}'
        )

        streams = await self._query_range(logql, start_ns, now_ns, limit=limit)

        all_lines: list[str] = []
        for stream in streams:
            for _ts, line in stream.get("values", []):
                all_lines.append(line)

        # Reverse so oldest-first (we queried backward)
        all_lines.reverse()

        error_lines = [l for l in all_lines if _ERROR_RE.search(l)]
        warn_lines = [l for l in all_lines if _WARN_RE.search(l)]

        logger.info(
            "Loki collected — pod=%s total=%d errors=%d warnings=%d",
            pod, len(all_lines), len(error_lines), len(warn_lines),
        )

        return LokiData(
            pod=pod,
            namespace=namespace,
            lines=all_lines[-100:],          # cap at 100 lines to keep prompt manageable
            error_lines=error_lines[-50:],
            warn_lines=warn_lines[-30:],
        )
