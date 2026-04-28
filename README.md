# 🤖 PostmortemAI — AI-Powered Kubernetes Incident Analyzer

> Detects incidents via Prometheus alerts → collects metrics + logs → sends to Claude AI → outputs structured postmortem reports automatically.

---

## Architecture

```
Prometheus ──alert──► Alertmanager ──webhook──► PostmortemAI Service
                                                      │
                              ┌───────────────────────┤
                              ▼                       ▼
                        Prometheus API           Loki API
                        (metrics)                (logs)
                              │                       │
                              └───────────┬───────────┘
                                          ▼
                                    Claude AI API
                                          │
                                          ▼
                                  Incident Report
                                  (stdout + .txt + .json)
```

---

## Folder Structure

```
postmortem-ai/
├── app/                          # Broken demo Node.js app
│   ├── index.js                  # App with /stress, /crash, /error endpoints
│   ├── package.json
│   └── Dockerfile
│
├── service/                      # FastAPI PostmortemAI service (core)
│   ├── main.py                   # FastAPI app, /alert webhook endpoint
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example
│   └── core/
│       ├── models.py             # Pydantic data models
│       ├── prometheus_client.py  # Fetches CPU, memory, restarts
│       ├── loki_client.py        # Fetches and classifies logs
│       ├── ai_analyzer.py        # Claude API integration + prompt
│       └── report_writer.py      # Formats and saves incident reports
│
├── k8s/
│   ├── app/
│   │   └── deployment.yaml       # Demo app Deployment + Service
│   ├── monitoring/
│   │   ├── alert-rules.yaml      # PrometheusRule CRD
│   │   └── alertmanager-config.yaml
│   └── service/
│       └── deployment.yaml       # PostmortemAI Service + Secret
│
└── scripts/
    ├── setup.sh                  # Full cluster + stack setup
    └── trigger-incident.sh       # Trigger CPU/crash/manual incidents
```

---

## Prerequisites

Install these before running:

```bash
# kind — local Kubernetes
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.23.0/kind-linux-amd64
chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/

# helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Docker Desktop or docker engine must be running
```

---

## 🚀 Setup (One Command)

```bash
git clone https://github.com/your-org/postmortem-ai
cd postmortem-ai

export ANTHROPIC_API_KEY="sk-ant-your-key-here"
chmod +x scripts/*.sh
./scripts/setup.sh
```

This will:
1. Create a 3-node kind cluster
2. Install `kube-prometheus-stack` (Prometheus + Alertmanager + Grafana)
3. Install `loki-stack` (Loki + Promtail)
4. Apply Prometheus alert rules
5. Build & load both Docker images into kind
6. Deploy the demo app and PostmortemAI service

---

## 🔥 Demo Flow (1 Minute)

### Option A — CPU Spike (realistic)
```bash
# Terminal 1: Watch AI logs
kubectl logs -f deploy/postmortem-ai-service

# Terminal 2: Trigger CPU stress
./scripts/trigger-incident.sh cpu

# Wait ~90 seconds for Prometheus to fire the alert.
# Alertmanager calls the webhook.
# PostmortemAI collects data, calls Claude, prints report.
```

### Option B — Instant Manual Test
```bash
# Terminal 1: Watch AI logs  
kubectl logs -f deploy/postmortem-ai-service

# Terminal 2: Send webhook directly
./scripts/trigger-incident.sh manual
# Report appears in ~10 seconds
```

### Option C — Crash Loop
```bash
./scripts/trigger-incident.sh crash
# Pod restarts → PodCrashLooping alert fires → analysis runs
```

---

## Sample Output

```
╔══════════════════════════════════════════════════════════════════════╗
║          🤖  POSTMORTEM AI — INCIDENT ANALYSIS REPORT               ║
╚══════════════════════════════════════════════════════════════════════╝

  Report ID   : INC-20250428143022-A3F9B1
  Generated   : 2025-04-28 14:30:22 UTC
  Status      : OPEN
────────────────────────────────────────────────────────────────────────
  INCIDENT     : HighCpuUsage
  Pod          : demo-broken-app-6d8f9b-xkp2n
  Namespace    : default
  Severity     : 🟠 HIGH
  Confidence   : ████████░░  82%
────────────────────────────────────────────────────────────────────────
  ROOT CAUSE
────────────────────────────────────────────────────────────────────────
  The pod is executing a tight synchronous CPU loop in its /stress
  handler without yielding to the event loop. The STRESS_CPU environment
  variable set to "true" triggers setInterval-based CPU burns every 4s,
  saturating the 500m CPU limit continuously.
...
  KUBERNETES FIX
────────────────────────────────────────────────────────────────────────
  apiVersion: autoscaling/v2
  kind: HorizontalPodAutoscaler
  ...
```

---

## Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/healthz` | GET | Liveness probe |
| `/readyz` | GET | Readiness probe |
| `/alert` | POST | Alertmanager webhook receiver |
| `/alert/test` | POST | Echo test for webhook debugging |
| `/reports` | GET | List all saved reports |
| `/reports/{id}` | GET | Fetch a specific report |

---

## Local Development (no Kubernetes)

```bash
cd service

# Port-forward Prometheus and Loki from your cluster
kubectl port-forward svc/kube-prometheus-stack-prometheus 9090:9090 -n monitoring &
kubectl port-forward svc/loki 3100:3100 -n monitoring &

# Set env vars
cp .env.example .env
# Edit .env with your API key

pip install -r requirements.txt
export $(cat .env | xargs)
uvicorn main:app --reload --port 8000

# In another terminal, send a test alert:
curl -X POST http://localhost:8000/alert/test -H "Content-Type: application/json" -d '{}'
```

---

## Configuration

| Env Var | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **Required.** Your Anthropic API key |
| `PROMETHEUS_URL` | `http://...prometheus:9090` | Prometheus endpoint |
| `LOKI_URL` | `http://...loki:3100` | Loki endpoint |
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Claude model to use |
| `LOG_LEVEL` | `INFO` | Python log level |
| `REPORTS_DIR` | `/tmp/postmortem-reports` | Where reports are saved |

---

## Extending PostmortemAI

- **Add Slack notifications**: Add a Slack webhook call in `report_writer.py` after `save_report()`
- **Add PagerDuty**: Use the PD Events API v2 in the same place
- **Add more alerts**: Extend `k8s/monitoring/alert-rules.yaml` with new `PrometheusRule` entries
- **Custom prompt**: Edit `SYSTEM_PROMPT` and `_build_user_prompt()` in `service/core/ai_analyzer.py`
- **Persist reports**: Replace `emptyDir` in `k8s/service/deployment.yaml` with a `PersistentVolumeClaim`
