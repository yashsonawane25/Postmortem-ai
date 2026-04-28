"""
AI Analyzer for PostmortemAI.
Sends structured observability context to Claude and parses the incident analysis.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime

import anthropic

from core.models import (
    IncidentAnalysis,
    ObservabilityContext,
    Severity,
)

logger = logging.getLogger(__name__)

# ── Prompt templates ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior Site Reliability Engineer (SRE) and Kubernetes expert performing \
a postmortem analysis. You receive structured observability data (metrics + logs) \
from a Kubernetes incident and must produce a precise, actionable analysis.

RESPONSE FORMAT — you MUST return a single valid JSON object with EXACTLY these keys:
{
  "severity":           "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "confidence_pct":     integer 0-100,
  "root_cause":         string — technical root cause in 2-4 sentences,
  "impact":             string — user/system impact in 1-3 sentences,
  "recommended_fix":    string — step-by-step remediation (numbered list as a single string),
  "kubernetes_fix_yaml": string — a complete, valid YAML snippet to fix the issue,
  "timeline":           string — brief incident timeline based on the data
}

RULES:
- Be precise and technical. No vague statements.
- kubernetes_fix_yaml must be real, apply-able YAML (not pseudo-code).
- confidence_pct reflects how certain you are given the data quality.
- If logs show OOMKilled, prioritise memory limits in your YAML fix.
- If CPU is saturated, prioritise HPA or resource limit adjustments.
- Do NOT wrap JSON in markdown code fences.
- Output ONLY the JSON object. No preamble, no explanation outside the JSON.
"""


def _build_user_prompt(ctx: ObservabilityContext) -> str:
    alert = ctx.alert
    prom = ctx.prometheus
    loki = ctx.loki

    # Format metric tables
    def fmt_metrics(samples, label="value"):
        if not samples:
            return "  No data collected."
        return "\n".join(
            f"  pod={s.pod}  {label}={s.value} {s.unit}" for s in samples
        )

    cpu_str = fmt_metrics(prom.cpu_usage, "cpu")
    mem_str = fmt_metrics(prom.memory_usage, "mem")
    restart_str = fmt_metrics(prom.restart_count, "restarts")
    error_rate_str = fmt_metrics(prom.error_rate, "err_rate")

    # Format log excerpts
    def fmt_logs(lines, cap=20):
        if not lines:
            return "  (none)"
        return "\n".join(f"  {l}" for l in lines[-cap:])

    error_logs = fmt_logs(loki.error_lines)
    warn_logs = fmt_logs(loki.warn_lines)
    recent_logs = fmt_logs(loki.lines[-30:])

    return f"""\
=== INCIDENT CONTEXT ===
Alert Name   : {alert.labels.alertname}
Status       : {alert.status}
Namespace    : {alert.labels.namespace}
Pod          : {alert.labels.pod}
Container    : {alert.labels.container}
Service      : {alert.labels.service}
Severity     : {alert.labels.severity}
Started At   : {alert.startsAt.isoformat()}
Summary      : {alert.annotations.summary}
Description  : {alert.annotations.description}

=== PROMETHEUS METRICS (last 5 minutes) ===
CPU Usage (cores):
{cpu_str}

Memory Usage:
{mem_str}

Restart Count:
{restart_str}

HTTP Error Rate (req/s):
{error_rate_str}

=== LOKI LOGS (last 30 minutes) ===
ERROR / FATAL lines:
{error_logs}

WARNING lines:
{warn_logs}

Recent log tail:
{recent_logs}

=== TASK ===
Analyse the above incident data and return a JSON postmortem report following \
the exact format specified in your system instructions.
"""


# ── Analyzer class ────────────────────────────────────────────────────────────

class AIAnalyzer:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def analyze(self, ctx: ObservabilityContext) -> IncidentAnalysis:
        """
        Call Claude synchronously (Anthropic SDK is sync by default).
        Returns a structured IncidentAnalysis.
        """
        user_prompt = _build_user_prompt(ctx)

        logger.info(
            "Sending analysis request to Claude model=%s alert=%s pod=%s",
            self.model,
            ctx.alert.labels.alertname,
            ctx.alert.labels.pod,
        )

        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw_text = message.content[0].text
        logger.debug("Claude raw response: %s", raw_text[:500])

        parsed = self._parse_response(raw_text)

        incident_id = f"INC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

        return IncidentAnalysis(
            incident_id=incident_id,
            alert_name=ctx.alert.labels.alertname,
            pod=ctx.alert.labels.pod,
            namespace=ctx.alert.labels.namespace,
            severity=Severity(parsed.get("severity", "MEDIUM")),
            confidence_pct=int(parsed.get("confidence_pct", 50)),
            root_cause=parsed.get("root_cause", "Unable to determine."),
            impact=parsed.get("impact", "Unknown impact."),
            recommended_fix=parsed.get("recommended_fix", "No recommendation."),
            kubernetes_fix_yaml=parsed.get("kubernetes_fix_yaml", ""),
            timeline=parsed.get("timeline", ""),
            raw_response=raw_text,
        )

    @staticmethod
    def _parse_response(raw: str) -> dict:
        """
        Robustly parse JSON from Claude's response.
        Strips accidental markdown fences if present.
        """
        # Strip markdown code fences if Claude forgot the rules
        cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("` ")

        # Find the outermost JSON object
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start == -1 or end == 0:
            logger.error("No JSON object found in Claude response")
            return {}

        json_str = cleaned[start:end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Claude JSON: %s\nRaw: %s", exc, json_str[:300])
            return {}
