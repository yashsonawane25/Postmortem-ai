"""
PostmortemAI — FastAPI Service
Receives Alertmanager webhooks, collects observability data,
calls NVIDIA OpenAI-compatible API for analysis, and saves structured incident reports.
"""

from __future__ import annotations

import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pydantic import BaseModel

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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
from core.db import (
    init_db,
    register_chaos_experiment,
    fail_chaos_experiment,
    update_chaos_status,
    get_chaos_status,
    get_resilience_score,
    save_ai_report,
    get_latest_ai_report,
    get_latest_cost_insights,
    generate_api_key,
    get_cluster_status,
    upsert_cluster_heartbeat
)
from auth import get_current_user, validate_api_key

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
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL   = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
LOG_LEVEL      = os.environ.get("LOG_LEVEL", "INFO")

logging.getLogger().setLevel(LOG_LEVEL)

# Multi-tenant cache for agent-pushed data
# Format: { tenant_id: { "metrics": {...}, "logs": {...} } }
CACHE = {}

# ── App lifecycle ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY is not set — AI analysis will fail.")
    logger.info("PostmortemAI service starting up")
    logger.info("Prometheus  : %s", PROMETHEUS_URL)
    logger.info("Loki        : %s", LOKI_URL)
    logger.info("Anthropic model: %s", ANTHROPIC_MODEL)
    
    # Initialize SQLite DB
    init_db()
    
    yield
    logger.info("PostmortemAI service shutting down")


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="PostmortemAI",
    description="AI-powered Kubernetes incident analysis service",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Client singletons ─────────────────────────────────────────────────────────
prom_client  = PrometheusClient(base_url=PROMETHEUS_URL)
loki_client  = LokiClient(base_url=LOKI_URL)
ai_analyzer  = AIAnalyzer(model=ANTHROPIC_MODEL)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/healthz", status_code=200)
@app.get("/health", status_code=200)
async def healthz():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/readyz", status_code=200)
async def readyz():
    """Kubernetes readiness probe."""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")
    return {"status": "ready"}


@app.post("/alert", status_code=202)
@limiter.limit("10/minute")
async def receive_alert(payload: AlertmanagerPayload, request: Request, tenant_id: str = Depends(validate_api_key)):
    """
    Primary webhook endpoint.
    Alertmanager POSTs here when an alert fires.
    """
    logger.info(
        "Received webhook: status=%s alerts=%d tenant_id=%s",
        payload.status,
        len(payload.alerts),
        tenant_id
    )

    # Only act on firing alerts
    firing_alerts = [a for a in payload.alerts if a.status == AlertStatus.FIRING]
    if not firing_alerts:
        logger.info("No firing alerts in payload — skipping.")
        return {"message": "No firing alerts, nothing to do."}

    results = []
    for alert in firing_alerts:
        # Check if this alert was triggered by chaos experiment
        if alert.labels.model_extra and alert.labels.model_extra.get("chaos_experiment") == "true":
            logger.info("Chaos experiment alert detected! Marking as FAILED.")
            fail_chaos_experiment(tenant_id)

        try:
            result = await _process_alert(alert, tenant_id)
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
async def list_reports(user: dict = Depends(get_current_user)):
    """List all saved incident reports for a tenant."""
    from pathlib import Path
    import os
    tenant_id = user["tenant_id"]
    reports_dir = Path(os.getenv("REPORTS_DIR", "/tmp/postmortem-reports")) / tenant_id
    if not reports_dir.exists():
        return {"reports": []}
    files = sorted(reports_dir.glob("*.txt"), reverse=True)
    return {"reports": [f.stem for f in files]}


@app.get("/reports/{report_id}", response_class=PlainTextResponse)
async def get_report(report_id: str, user: dict = Depends(get_current_user)):
    """Fetch a saved report by ID."""
    from pathlib import Path
    import os
    tenant_id = user["tenant_id"]
    reports_dir = Path(os.getenv("REPORTS_DIR", "/tmp/postmortem-reports")) / tenant_id
    report_file = reports_dir / f"{report_id}.txt"
    if not report_file.exists():
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return report_file.read_text()


# ── Dashboard Endpoints ───────────────────────────────────────────────────────

@app.get("/cluster-status")
async def api_get_cluster_status(user: dict = Depends(get_current_user)):
    return get_cluster_status(user["tenant_id"])

@app.post("/api/keys")
@limiter.limit("5/minute")
async def api_generate_key(request: Request, user: dict = Depends(get_current_user)):
    key = generate_api_key(user["tenant_id"])
    return {"api_key": key}

@app.post("/agent/heartbeat")
async def agent_heartbeat(tenant_id: str = Depends(validate_api_key)):
    upsert_cluster_heartbeat(tenant_id)
    return {"status": "ok"}

@app.post("/agent/metrics")
async def agent_metrics(payload: dict, tenant_id: str = Depends(validate_api_key)):
    upsert_cluster_heartbeat(tenant_id)
    if tenant_id not in CACHE:
        CACHE[tenant_id] = {"metrics": None, "logs": None}
    CACHE[tenant_id]["metrics"] = payload
    return {"status": "ok"}

@app.post("/agent/logs")
async def agent_logs(payload: dict, tenant_id: str = Depends(validate_api_key)):
    upsert_cluster_heartbeat(tenant_id)
    if tenant_id not in CACHE:
        CACHE[tenant_id] = {"metrics": None, "logs": None}
    CACHE[tenant_id]["logs"] = payload
    return {"status": "ok"}

@app.get("/metrics")
async def get_dashboard_metrics(user: dict = Depends(get_current_user)):
    """Returns cached metrics pushed by the agent for the frontend dashboard."""
    tenant_id = user["tenant_id"]
    if tenant_id in CACHE and CACHE[tenant_id]["metrics"]:
        return CACHE[tenant_id]["metrics"]["metrics"]
    return {"cpu_cores": 0, "memory_mib": 0}

@app.get("/logs")
async def get_dashboard_logs(user: dict = Depends(get_current_user)):
    """Returns cached recent logs pushed by the agent for the frontend dashboard."""
    tenant_id = user["tenant_id"]
    if tenant_id in CACHE and CACHE[tenant_id]["logs"]:
        return CACHE[tenant_id]["logs"]
    return {"logs": []}

@app.get("/ai-report")
async def api_get_ai_report(user: dict = Depends(get_current_user)):
    report = get_latest_ai_report(user["tenant_id"])
    if not report:
        return {"status": "no_reports"}
    return report

@app.get("/chaos-status")
async def get_chaos(user: dict = Depends(get_current_user)):
    """Get the history of chaos experiments."""
    return get_chaos_status(user["tenant_id"])

@app.get("/resilience-score")
async def get_resilience(user: dict = Depends(get_current_user)):
    """Get the resilience score."""
    return get_resilience_score(user["tenant_id"])

@app.get("/cost-insights")
async def get_cost_insights(user: dict = Depends(get_current_user)):
    """Get the latest cost insights per namespace."""
    return get_latest_cost_insights(user["tenant_id"])

class ChaosRegisterPayload(BaseModel):
    experiment_id: str
    target_pod: str

@app.post("/chaos/register")
async def api_register_chaos(payload: ChaosRegisterPayload, tenant_id: str = Depends(validate_api_key)):
    register_chaos_experiment(payload.experiment_id, payload.target_pod, tenant_id)
    return {"status": "registered", "experiment_id": payload.experiment_id}

class ChaosUpdatePayload(BaseModel):
    experiment_id: str
    status: str

@app.post("/chaos/update")
async def api_update_chaos(payload: ChaosUpdatePayload, tenant_id: str = Depends(validate_api_key)):
    update_chaos_status(payload.experiment_id, payload.status, tenant_id)
    return {"status": "updated", "experiment_id": payload.experiment_id}


# ── Core processing logic ─────────────────────────────────────────────────────

async def _process_alert(alert: Alert, tenant_id: str) -> dict:
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
    report, report_path = save_report(analysis, ctx, tenant_id)
    formatted = format_report(report)

    # Print to stdout so it shows in kubectl logs
    print(formatted)
    
    # Save to SQLite for Dashboard
    save_ai_report(
        analysis.incident_id, 
        alert.labels.alertname, 
        analysis.severity.value, 
        analysis.model_dump(),
        tenant_id
    )

    return {
        "incident_id": analysis.incident_id,
        "severity": analysis.severity.value,
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
