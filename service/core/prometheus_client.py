"""
Prometheus client for PostmortemAI.
Fetches CPU, memory, restart counts, and error-rate metrics for a given pod.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from core.models import MetricSample, PrometheusData

logger = logging.getLogger(__name__)


class PrometheusClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ── Low-level query ──────────────────────────────────────────────────────

    async def _instant_query(self, promql: str) -> list[dict[str, Any]]:
        """Execute a Prometheus instant query and return the result list."""
        url = f"{self.base_url}/api/v1/query"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params={"query": promql})
                resp.raise_for_status()
                body = resp.json()

            if body.get("status") != "success":
                logger.warning("Prometheus query returned non-success: %s", body)
                return []

            return body.get("data", {}).get("result", [])

        except httpx.HTTPError as exc:
            logger.error("Prometheus HTTP error for query '%s': %s", promql, exc)
            return []

    # ── Specific metric helpers ──────────────────────────────────────────────

    async def get_cpu_usage(self, namespace: str, pod: str) -> list[MetricSample]:
        """Rate of CPU seconds over the last 5 minutes (cores)."""
        promql = (
            f'rate(container_cpu_usage_seconds_total{{'
            f'namespace="{namespace}",pod=~"{pod}.*",container!=""}}'
            f'[5m])'
        )
        results = await self._instant_query(promql)
        return [
            MetricSample(
                pod=r["metric"].get("pod", pod),
                namespace=r["metric"].get("namespace", namespace),
                value=round(float(r["value"][1]), 4),
                unit="cores",
            )
            for r in results
        ]

    async def get_memory_usage(self, namespace: str, pod: str) -> list[MetricSample]:
        """Working set memory in MiB."""
        promql = (
            f'container_memory_working_set_bytes{{'
            f'namespace="{namespace}",pod=~"{pod}.*",container!=""}}'
        )
        results = await self._instant_query(promql)
        return [
            MetricSample(
                pod=r["metric"].get("pod", pod),
                namespace=r["metric"].get("namespace", namespace),
                value=round(float(r["value"][1]) / 1024 / 1024, 2),
                unit="MiB",
            )
            for r in results
        ]

    async def get_restart_count(self, namespace: str, pod: str) -> list[MetricSample]:
        """Total container restarts for the pod."""
        promql = (
            f'kube_pod_container_status_restarts_total{{'
            f'namespace="{namespace}",pod=~"{pod}.*"}}'
        )
        results = await self._instant_query(promql)
        return [
            MetricSample(
                pod=r["metric"].get("pod", pod),
                namespace=r["metric"].get("namespace", namespace),
                value=float(r["value"][1]),
                unit="restarts",
            )
            for r in results
        ]

    async def get_http_error_rate(self, namespace: str, pod: str) -> list[MetricSample]:
        """HTTP 5xx rate per second over last 5 minutes (if instrumented)."""
        promql = (
            f'rate(http_requests_total{{'
            f'namespace="{namespace}",pod=~"{pod}.*",status=~"5.."}}'
            f'[5m])'
        )
        results = await self._instant_query(promql)
        return [
            MetricSample(
                pod=r["metric"].get("pod", pod),
                namespace=r["metric"].get("namespace", namespace),
                value=round(float(r["value"][1]), 4),
                unit="req/s",
            )
            for r in results
        ]

    # ── Composite fetch ──────────────────────────────────────────────────────

    async def collect(self, namespace: str, pod: str) -> PrometheusData:
        """Fetch all relevant metrics for the given pod in parallel."""
        import asyncio

        cpu, mem, restarts, errors = await asyncio.gather(
            self.get_cpu_usage(namespace, pod),
            self.get_memory_usage(namespace, pod),
            self.get_restart_count(namespace, pod),
            self.get_http_error_rate(namespace, pod),
        )

        logger.info(
            "Prometheus collected — pod=%s cpu=%d mem=%d restarts=%d",
            pod, len(cpu), len(mem), len(restarts),
        )

        return PrometheusData(
            cpu_usage=cpu,
            memory_usage=mem,
            restart_count=restarts,
            error_rate=errors,
        )
