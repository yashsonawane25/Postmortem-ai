"""
Report writer for PostmortemAI.
Formats and persists incident reports to disk.
"""

from __future__ import annotations

import json
import logging
import os
import textwrap
import uuid
from datetime import datetime
from pathlib import Path

from core.models import IncidentAnalysis, IncidentReport, ObservabilityContext

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "/tmp/postmortem-reports"))


def _severity_emoji(severity: str) -> str:
    return {
        "CRITICAL": "🔴",
        "HIGH": "🟠",
        "MEDIUM": "🟡",
        "LOW": "🟢",
    }.get(severity.upper(), "⚪")


def _confidence_bar(pct: int) -> str:
    filled = round(pct / 10)
    return "█" * filled + "░" * (10 - filled) + f"  {pct}%"


def format_report(report: IncidentReport) -> str:
    a = report.analysis
    sep = "─" * 72
    emoji = _severity_emoji(a.severity)

    lines = [
        "",
        "╔══════════════════════════════════════════════════════════════════════╗",
        f"║          🤖  POSTMORTEM AI — INCIDENT ANALYSIS REPORT               ║",
        "╚══════════════════════════════════════════════════════════════════════╝",
        "",
        f"  Report ID   : {report.report_id}",
        f"  Generated   : {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"  Status      : {report.status.upper()}",
        sep,
        "",
        f"  INCIDENT     : {a.alert_name}",
        f"  Pod          : {a.pod}",
        f"  Namespace    : {a.namespace}",
        f"  Severity     : {emoji} {a.severity}",
        f"  Confidence   : {_confidence_bar(a.confidence_pct)}",
        "",
        sep,
        "  ROOT CAUSE",
        sep,
        textwrap.fill(a.root_cause, width=70, initial_indent="  ", subsequent_indent="  "),
        "",
        sep,
        "  IMPACT",
        sep,
        textwrap.fill(a.impact, width=70, initial_indent="  ", subsequent_indent="  "),
        "",
        sep,
        "  TIMELINE",
        sep,
        textwrap.fill(a.timeline, width=70, initial_indent="  ", subsequent_indent="  "),
        "",
        sep,
        "  RECOMMENDED FIX",
        sep,
        "",
    ]

    for line in a.recommended_fix.split("\n"):
        lines.append(f"  {line}")

    lines += [
        "",
        sep,
        "  KUBERNETES FIX (apply with: kubectl apply -f -)",
        sep,
        "",
    ]

    for line in a.kubernetes_fix_yaml.split("\n"):
        lines.append(f"  {line}")

    lines += [
        "",
        "══════════════════════════════════════════════════════════════════════",
        "",
    ]

    return "\n".join(lines)


def save_report(analysis: IncidentAnalysis, ctx: ObservabilityContext) -> tuple[IncidentReport, Path]:
    """
    Build an IncidentReport, format it, and write it to disk.
    Returns (report, file_path).
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report = IncidentReport(
        report_id=analysis.incident_id,
        analysis=analysis,
        observability_summary={
            "cpu_samples": len(ctx.prometheus.cpu_usage),
            "memory_samples": len(ctx.prometheus.memory_usage),
            "restart_samples": len(ctx.prometheus.restart_count),
            "log_lines": len(ctx.loki.lines),
            "error_lines": len(ctx.loki.error_lines),
            "warn_lines": len(ctx.loki.warn_lines),
        },
    )

    # ── Human-readable text report ──
    text_path = REPORTS_DIR / f"{analysis.incident_id}.txt"
    text_path.write_text(format_report(report), encoding="utf-8")
    logger.info("Saved text report → %s", text_path)

    # ── Machine-readable JSON report ──
    json_path = REPORTS_DIR / f"{analysis.incident_id}.json"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Saved JSON report → %s", json_path)

    return report, text_path
