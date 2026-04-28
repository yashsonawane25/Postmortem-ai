"""
PostmortemAI — FastAPI Service
Receives Alertmanager webhooks, collects observability data,
calls Claude for analysis, and saves structured incident reports.
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse

from core.ai_analyzer import AIAnalyzer
from core.loki_client import LokiClient
from core.models import (
    Alert,
    AlertmanagerPayload,
    AlertStatus,
    ObservabilityContext,
)
from core.prometheus_client import PrometheusClient
from core.report_writer import format_report, save_report

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("postmortem-ai")


# ── Config from environment ───────────────────────────────────────────────────
PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus-operated.monitoring.svc.cluster.local:9090")
LOKI_URL       = os.environ.get("LOKI_URL",       "http://loki.monitoring.svc.cluster.local:3100")
ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL   = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
LOG_LEVEL      = os.environ.get("LOG_LEVEL", "INFO")

logging.getLogger().setLevel(LOG_LEVEL)


# ── App lifecycle ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not ANTHROPIC_KEY:
        logger.error("ANTHROPIC_API_KEY is not set — AI analysis will fail.")
    logger.info("PostmortemAI service starting up")
    logger.info("Prometheus  : %s", PROMETHEUS_URL)
    logger.info("Loki        : %s", LOKI_URL)
    logger.info("Claude model: %s", CLAUDE_MODEL)
    yield
    logger.info("PostmortemAI service shutting down")


app = FastAPI(
    title="PostmortemAI",
    description="AI-powered Kubernetes incident analysis service",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Client singletons ─────────────────────────────────────────────────────────
prom_client  = PrometheusClient(base_url=PROMETHEUS_URL)
loki_client  = LokiClient(base_url=LOKI_URL)
ai_analyzer  = AIAnalyzer(api_key=ANTHROPIC_KEY, model=CLAUDE_MODEL)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/healthz", status_code=200)
async def healthz():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/readyz", status_code=200)
async def readyz():
    """Kubernetes readiness probe."""
    if not ANTHROPIC_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")
    return {"status": "ready"}


@app.post("/alert", status_code=202)
async def receive_alert(payload: AlertmanagerPayload, request: Request):
    """
    Primary webhook endpoint.
    Alertmanager POSTs here when an alert fires.
    """
    logger.info(
        "Received webhook: status=%s alerts=%d",
        payload.status,
        len(payload.alerts),
    )

    # Only act on firing alerts
    firing_alerts = [a for a in payload.alerts if a.status == AlertStatus.FIRING]
    if not firing_alerts:
        logger.info("No firing alerts in payload — skipping.")
        return {"message": "No firing alerts, nothing to do."}

    results = []
    for alert in firing_alerts:
        try:
            result = await _process_alert(alert)
            results.append(result)
        except Exception as exc:
            logger.exception("Failed to process alert %s: %s", alert.labels.alertname, exc)
            results.append({"error": str(exc), "alert": alert.labels.alertname})

    return {"processed": len(results), "results": results}


@app.post("/alert/test", status_code=200)
async def test_alert(request: Request):
    """
    Test endpoint — accepts raw JSON and pretty-prints the parsed payload.
    Useful for debugging Alertmanager webhook config.
    """
    body = await request.json()
    return JSONResponse(content={"received": body, "status": "ok"})


@app.get("/reports", status_code=200)
async def list_reports():
    """List all saved incident reports."""
    from pathlib import Path
    import os
    reports_dir = Path(os.getenv("REPORTS_DIR", "/tmp/postmortem-reports"))
    if not reports_dir.exists():
        return {"reports": []}
    files = sorted(reports_dir.glob("*.txt"), reverse=True)
    return {"reports": [f.stem for f in files]}


@app.get("/reports/{report_id}", response_class=PlainTextResponse)
async def get_report(report_id: str):
    """Fetch a saved report by ID."""
    from pathlib import Path
    import os
    reports_dir = Path(os.getenv("REPORTS_DIR", "/tmp/postmortem-reports"))
    report_file = reports_dir / f"{report_id}.txt"
    if not report_file.exists():
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return report_file.read_text()


# ── Core processing logic ─────────────────────────────────────────────────────

async def _process_alert(alert: Alert) -> dict:
    namespace = alert.labels.namespace or "default"
    pod       = alert.labels.pod or alert.labels.service or "unknown"

    logger.info(
        "Processing alert: name=%s pod=%s namespace=%s severity=%s",
        alert.labels.alertname, pod, namespace, alert.labels.severity,
    )

    # ── Step 1: Collect metrics and logs in parallel ──
    import asyncio
    prom_data, loki_data = await asyncio.gather(
        prom_client.collect(namespace=namespace, pod=pod),
        loki_client.collect(namespace=namespace, pod=pod),
    )

    ctx = ObservabilityContext(
        alert=alert,
        prometheus=prom_data,
        loki=loki_data,
    )

    logger.info(
        "Observability collected — cpu_samples=%d log_lines=%d error_lines=%d",
        len(prom_data.cpu_usage),
        len(loki_data.lines),
        len(loki_data.error_lines),
    )

    # ── Step 2: AI analysis ──
    analysis = ai_analyzer.analyze(ctx)

    logger.info(
        "Analysis complete — incident_id=%s severity=%s confidence=%d%%",
        analysis.incident_id,
        analysis.severity,
        analysis.confidence_pct,
    )

    # ── Step 3: Save and print report ──
    report, report_path = save_report(analysis, ctx)
    formatted = format_report(report)

    # Print to stdout so it shows in kubectl logs
    print(formatted)

    return {
        "incident_id": analysis.incident_id,
        "severity": analysis.severity,
        "confidence_pct": analysis.confidence_pct,
        "report_path": str(report_path),
        "root_cause": analysis.root_cause[:200],
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        access_log=True,
    )
