#!/usr/bin/env bash
# =============================================================================
# PostmortemAI — Full Setup Script
# Run: chmod +x scripts/setup.sh && ./scripts/setup.sh
# =============================================================================
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Config ────────────────────────────────────────────────────────────────────
CLUSTER_NAME="postmortem-ai"
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# ── Prerequisite check ────────────────────────────────────────────────────────
check_tool() {
  command -v "$1" &>/dev/null || error "$1 is not installed. Please install it first."
}

info "Checking prerequisites..."
check_tool kind
check_tool kubectl
check_tool helm
check_tool docker
ok "All prerequisites found."

# ── API key check ─────────────────────────────────────────────────────────────
if [[ -z "$ANTHROPIC_API_KEY" ]]; then
  echo -e "${YELLOW}Enter your Anthropic API key (starts with sk-ant-):${NC}"
  read -r -s ANTHROPIC_API_KEY
  echo
fi
[[ "$ANTHROPIC_API_KEY" == sk-ant-* ]] || warn "API key doesn't look like an Anthropic key."

# ── Step 1: Create kind cluster ───────────────────────────────────────────────
info "Step 1: Creating kind cluster '$CLUSTER_NAME'..."

if kind get clusters | grep -q "^$CLUSTER_NAME$"; then
  warn "Cluster '$CLUSTER_NAME' already exists — skipping creation."
else
  cat <<EOF | kind create cluster --name "$CLUSTER_NAME" --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    kubeadmConfigPatches:
      - |
        kind: InitConfiguration
        nodeRegistration:
          kubeletExtraArgs:
            node-labels: "ingress-ready=true"
  - role: worker
  - role: worker
EOF
  ok "Cluster '$CLUSTER_NAME' created."
fi

kubectl cluster-info --context "kind-$CLUSTER_NAME"

# ── Step 2: Install kube-prometheus-stack ─────────────────────────────────────
info "Step 2: Installing kube-prometheus-stack..."

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
  --set prometheus.prometheusSpec.ruleSelectorNilUsesHelmValues=false \
  --set alertmanager.config.global.resolve_timeout=5m \
  --set alertmanager.config.route.receiver=postmortem-ai-webhook \
  --set-json 'alertmanager.config.route.routes=[
    {"match":{"severity":"critical"},"receiver":"postmortem-ai-webhook"},
    {"match":{"severity":"warning"},"receiver":"postmortem-ai-webhook"}
  ]' \
  --set-json 'alertmanager.config.receivers=[{
    "name":"postmortem-ai-webhook",
    "webhook_configs":[{
      "url":"http://postmortem-ai-service.default.svc.cluster.local:8000/alert",
      "send_resolved":true
    }]
  }]' \
  --wait --timeout=300s

ok "kube-prometheus-stack installed."

# ── Step 3: Install Loki stack ────────────────────────────────────────────────
info "Step 3: Installing Loki stack..."

helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm upgrade --install loki grafana/loki-stack \
  --namespace monitoring \
  --set promtail.enabled=true \
  --set grafana.enabled=false \
  --wait --timeout=300s

ok "Loki stack installed."

# ── Step 4: Apply Prometheus alert rules ─────────────────────────────────────
info "Step 4: Applying Prometheus alert rules..."
kubectl apply -f "$ROOT_DIR/k8s/monitoring/alert-rules.yaml"
ok "Alert rules applied."

# ── Step 5: Build and load demo app image ────────────────────────────────────
info "Step 5: Building demo-broken-app Docker image..."
docker build -t demo-broken-app:latest "$ROOT_DIR/app/"
kind load docker-image demo-broken-app:latest --name "$CLUSTER_NAME"
ok "demo-broken-app image loaded into kind."

# ── Step 6: Deploy demo app ───────────────────────────────────────────────────
info "Step 6: Deploying demo-broken-app..."
kubectl apply -f "$ROOT_DIR/k8s/app/deployment.yaml"
kubectl rollout status deployment/demo-broken-app --timeout=60s
ok "demo-broken-app deployed."

# ── Step 7: Build and load PostmortemAI service image ────────────────────────
info "Step 7: Building postmortem-ai-service Docker image..."
docker build -t postmortem-ai-service:latest "$ROOT_DIR/service/"
kind load docker-image postmortem-ai-service:latest --name "$CLUSTER_NAME"
ok "postmortem-ai-service image loaded into kind."

# ── Step 8: Create API key secret and deploy service ─────────────────────────
info "Step 8: Deploying PostmortemAI service..."

# Patch the secret with the real API key
kubectl create secret generic postmortem-ai-secrets \
  --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# Apply the deployment (but replace the placeholder secret block)
kubectl apply -f "$ROOT_DIR/k8s/service/deployment.yaml"
kubectl rollout status deployment/postmortem-ai-service --timeout=60s
ok "PostmortemAI service deployed."

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           PostmortemAI Setup Complete! 🎉                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Next steps:"
echo "  1. Trigger an incident:    ./scripts/trigger-incident.sh"
echo "  2. Watch AI analysis:      kubectl logs -f deploy/postmortem-ai-service"
echo "  3. Port-forward service:   kubectl port-forward svc/postmortem-ai-service 8000:8000"
echo ""
