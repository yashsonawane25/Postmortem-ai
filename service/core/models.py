"""
Data models for PostmortemAI.
All incoming Alertmanager payloads and outgoing analysis results are typed here.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Alertmanager Webhook Payload ────────────────────────────────────────────

class AlertStatus(str, Enum):
    FIRING = "firing"
    RESOLVED = "resolved"


class AlertLabel(BaseModel):
    alertname: str = ""
    namespace: str = "default"
    pod: str = ""
    container: str = ""
    service: str = ""
    severity: str = "unknown"
    team: str = ""

    # Allow any extra Prometheus labels
    model_config = {"extra": "allow"}


class AlertAnnotation(BaseModel):
    summary: str = ""
    description: str = ""
    runbook_url: str = ""

    model_config = {"extra": "allow"}


class Alert(BaseModel):
    status: AlertStatus
    labels: AlertLabel
    annotations: AlertAnnotation
    startsAt: datetime
    endsAt: datetime
    generatorURL: str = ""
    fingerprint: str = ""


class AlertmanagerPayload(BaseModel):
    """Exact shape Alertmanager sends to a webhook receiver."""
    version: str = "4"
    groupKey: str = ""
    truncatedAlerts: int = 0
    status: AlertStatus
    receiver: str = ""
    groupLabels: dict[str, str] = Field(default_factory=dict)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    externalURL: str = ""
    alerts: list[Alert] = Field(default_factory=list)


# ── Collected Observability Data ────────────────────────────────────────────

class MetricSample(BaseModel):
    pod: str
    namespace: str
    value: float
    unit: str = ""


class PrometheusData(BaseModel):
    cpu_usage: list[MetricSample] = Field(default_factory=list)
    memory_usage: list[MetricSample] = Field(default_factory=list)
    restart_count: list[MetricSample] = Field(default_factory=list)
    error_rate: list[MetricSample] = Field(default_factory=list)
    raw_queries: dict[str, Any] = Field(default_factory=dict)


class LokiData(BaseModel):
    pod: str
    namespace: str
    lines: list[str] = Field(default_factory=list)
    error_lines: list[str] = Field(default_factory=list)
    warn_lines: list[str] = Field(default_factory=list)


class ObservabilityContext(BaseModel):
    alert: Alert
    prometheus: PrometheusData
    loki: LokiData
    collected_at: datetime = Field(default_factory=datetime.utcnow)


# ── AI Analysis Result ───────────────────────────────────────────────────────

class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentAnalysis(BaseModel):
    """Structured output from the AI analysis."""
    incident_id: str
    alert_name: str
    pod: str
    namespace: str
    severity: Severity
    confidence_pct: int = Field(ge=0, le=100)
    root_cause: str
    impact: str
    recommended_fix: str
    kubernetes_fix_yaml: str
    timeline: str
    weakness_explanation: str = ""
    resilience_improvement: str = ""
    monitoring_improvement: str = ""
    cost_insight: str = ""
    savings_recommendation: str = ""
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    raw_response: str = ""


# ── Incident Report ──────────────────────────────────────────────────────────

class IncidentReport(BaseModel):
    report_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    analysis: IncidentAnalysis
    observability_summary: dict[str, Any] = Field(default_factory=dict)
    status: str = "open"
