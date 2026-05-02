# 🤖 PostmortemAI — Autonomous SRE Platform

> An end-to-end autonomous SRE platform built across five phases. Detects incidents via Prometheus alerts, injects automated chaos experiments to test resilience, tracks real-time cost metrics via OpenCost, and leverages AI (Claude / NVIDIA API) to provide actionable, structured postmortem reports and FinOps recommendations. Transformed into a fully multi-tenant SaaS architecture with cluster onboarding and secure agent communication.

---

## 🏗️ Architecture

```text
       [ Target Kubernetes Cluster ]                        [ PostmortemAI SaaS Platform ]
                                                                 
 Prometheus ──┐                                             ┌──► React Dashboard (Clerk Auth)
              │    ┌───────────────┐        API Key         │          │
 OpenCost  ───┼───►│ SRE Agent     ├────────────────────────┤          ▼
              │    └───────────────┘  (Metrics, Logs, Cost) │    FastAPI Backend
 Loki      ───┘                                             │    (Multi-tenant DB)
                                                            │          │
                                                            └──────────┼─────────► AI API (Claude / NVIDIA)
```

---

## 📂 Folder Structure

```text
postmortem-ai/
├── agent/                        # Phase 4: Autonomous SRE Agent (Python)
├── app/                          # Broken demo Node.js app
├── chaos/                        # Chaos engineering scripts & manifests
├── cost/                         # OpenCost data fetching loop
├── frontend/                     # React + Tailwind Dashboard (Clerk Auth integrated)
├── k8s/                          # Kubernetes deployment manifests
├── monitoring/                   # Prometheus & Alertmanager configs + SLO checker
├── scripts/                      # Setup and trigger scripts
└── service/                      # FastAPI Backend Service (Core Engine, Multi-tenant)
```

---

## 🛠️ Prerequisites

Install these tools before running:

1. **kind** — Local Kubernetes cluster
2. **kubectl** — Kubernetes command-line tool
3. **helm** — Kubernetes package manager
4. **docker** — Container engine
5. **Node.js & npm** — For running the React dashboard

---

## 🚀 Setup (One Command)

To deploy the entire stack (Monitoring, Loki, OpenCost, FastAPI, and Demo App):

```bash
git clone https://github.com/your-org/postmortem-ai
cd postmortem-ai

# You will be prompted for your Anthropic API Key during setup
chmod +x scripts/*.sh
./scripts/setup.sh
```

This will:
1. Create a 3-node `kind` cluster named `postmortem-ai`
2. Install `kube-prometheus-stack` and `loki-stack`
3. Install `opencost/opencost` for cost metrics
4. Build and deploy the demo app and PostmortemAI backend service
5. Port-forward the backend to `http://localhost:8000`
6. Start the frontend React dashboard at `http://localhost:5173`

---

## 🌟 Phase 1: Incident Analysis Engine

When a Prometheus alert fires (e.g., CPU Spike or CrashLoopBackOff), the `Alertmanager` sends a webhook to the FastAPI backend.
The backend collects the last 5 minutes of metrics and 30 minutes of logs, and sends them to the Anthropic Claude API to generate a structured JSON postmortem containing the root cause, impact, and a deployable Kubernetes YAML fix.

**Test it:**
```bash
# Trigger CPU stress
./scripts/trigger-incident.sh cpu

# Check the dashboard for the new incident report!
```

---

## 🌪️ Phase 2: ChaosGuard Integration

Turning reactive analysis into proactive resilience testing. Chaos experiments are automatically injected, and the system is scored based on how well it recovers.

- **Automated Chaos Testing**: Scripts to delete random pods and stress the system.
- **AI Chaos Insights**: AI detects the chaos test and specifically suggests resilience improvements.
- **Weekly Resilience Score**: Tracked in the React dashboard.

**Test it:**
```bash
./chaos/random-pod-kill.sh
```

---

## 💰 Phase 3: FinOps Engine

Integrating cost intelligence directly into the SRE workflow.

- **OpenCost Integration**: Automatically scrapes Kubernetes node and pod resource allocations.
- **Cost Engine Backend**: Syncs cost metrics into the SQLite DB.
- **AI Savings Recommendations**: During an incident, the AI looks at the namespace's cost efficiency and provides tailored scaling recommendations to reduce wasted spend.
- **FinOps Dashboard Panel**: A real-time view of cluster costs, efficiency bars, and AI recommendations.

---

## 🤖 Phase 4: Autonomous SRE Agent

A decentralized approach moving from a monolithic scraper to an edge-deployed agent (`agent/agent.py`).

- **Metrics & Logs Push**: Gathers system metrics and Loki logs locally within the target cluster, securely pushing them to the central SaaS platform.
- **Heartbeat Mechanism**: Continuously signals cluster health to the central control plane.
- **Lightweight Deployment**: Packaged for easy installation in target clusters, communicating back to the FastAPI backend via secure REST endpoints.

---

## 🏢 Phase 5: SaaS Multi-Tenancy Architecture

Transforming the standalone platform into a multi-tenant SaaS product.

- **User Authentication**: Integrated Clerk in the React dashboard for seamless and secure user authentication and tenant onboarding.
- **Tenant Data Isolation**: The backend SQLite database maps API keys to `tenant_id`s, ensuring incidents, chaos experiments, and cost metrics are strictly isolated.
- **Cluster Onboarding Workflow**: A dedicated "Connect Your Cluster" UI allows new users to dynamically generate secure API keys and copy Helm deployment commands to connect their clusters.
- **Real-time Connection State**: The dashboard conditionally renders the full monitoring suite only once a successful agent heartbeat is detected for the active tenant.

---

## 💻 The Dashboard

Access the React dashboard at `http://localhost:5173`.
It features:
- **Authentication**: Secure login/signup via Clerk.
- **Cluster Connection**: UI to generate API keys for the SRE agent.
- **KPI Cards**: Resilience Score, Total Experiments, System CPU, and Cluster Cost.
- **AI Incident Insights**: Real-time display of the latest AI-generated postmortem.
- **System Health Chart**: Live CPU & Memory tracking.
- **Chaos Experiments Log**: History of automated resilience tests.
- **Live Logs (Loki)**: Live streaming logs of the cluster.
- **FinOps & Cost Panel**: Namespace cost breakdown and AI-driven savings recommendations.

---

## 🔧 Troubleshooting

If setup fails or gets stuck:
- Ensure Docker is running.
- Provide a valid `ANTHROPIC_API_KEY` when prompted by `setup.sh`.
- View backend logs: `kubectl logs -f deploy/postmortem-ai-service`
