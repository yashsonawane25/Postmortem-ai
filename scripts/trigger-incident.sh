#!/usr/bin/env bash
# =============================================================================
# PostmortemAI — Trigger an Incident for Demo
# Causes CPU spike → Prometheus alert fires → Alertmanager calls webhook →
# PostmortemAI collects data → NVIDIA AI analyzes → Report saved
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }

INCIDENT_TYPE="${1:-cpu}"   # cpu | crash | manual

case "$INCIDENT_TYPE" in

  # ── CPU Spike ──────────────────────────────────────────────────────────────
  cpu)
    info "Triggering CPU stress on demo-broken-app..."
    info "Patching deployment to enable STRESS_CPU=true..."

    kubectl set env deployment/demo-broken-app STRESS_CPU=true
    kubectl rollout status deployment/demo-broken-app --timeout=60s
    ok "CPU stress enabled. Prometheus should alert within ~2 minutes."
    echo ""
    echo "  Watch alert fire:    kubectl port-forward svc/kube-prometheus-stack-alertmanager 9093:9093 -n monitoring"
    echo "  Then open:           http://localhost:9093"
    echo ""
    echo "  Watch AI analysis:   kubectl logs -f deploy/postmortem-ai-service"
    echo ""
    warn "To stop the stress:  kubectl set env deployment/demo-broken-app STRESS_CPU=false"
    ;;

  # ── Crash Loop ─────────────────────────────────────────────────────────────
  crash)
    info "Triggering crash loop on demo-broken-app..."
    POD=$(kubectl get pods -l app=demo-broken-app -o jsonpath='{.items[0].metadata.name}')
    info "Hitting /crash on pod $POD..."
    kubectl exec "$POD" -- wget -qO- http://localhost:3000/crash || true
    ok "Pod should restart. Watch: kubectl get pods -w"
    ;;

  # ── Manual Webhook Test ────────────────────────────────────────────────────
  manual)
    info "Sending manual test webhook to PostmortemAI service..."

    # Port-forward in background
    kubectl port-forward svc/postmortem-ai-service 8000:8000 &
    PF_PID=$!
    sleep 2

    POD_NAME=$(kubectl get pods -l app=demo-broken-app -o jsonpath='{.items[0].metadata.name}')

    curl -s -X POST http://localhost:8000/alert \
      -H "Content-Type: application/json" \
      -d "{
        \"version\": \"4\",
        \"groupKey\": \"test-group\",
        \"truncatedAlerts\": 0,
        \"status\": \"firing\",
        \"receiver\": \"postmortem-ai-webhook\",
        \"groupLabels\": {\"alertname\": \"HighCpuUsage\"},
        \"commonLabels\": {\"alertname\": \"HighCpuUsage\", \"severity\": \"warning\"},
        \"commonAnnotations\": {\"summary\": \"High CPU on demo pod\"},
        \"externalURL\": \"http://alertmanager:9093\",
        \"alerts\": [
          {
            \"status\": \"firing\",
            \"labels\": {
              \"alertname\": \"HighCpuUsage\",
              \"namespace\": \"default\",
              \"pod\": \"$POD_NAME\",
              \"container\": \"demo-broken-app\",
              \"service\": \"demo-broken-app\",
              \"severity\": \"warning\",
              \"team\": \"platform\"
            },
            \"annotations\": {
              \"summary\": \"High CPU usage on pod $POD_NAME\",
              \"description\": \"Pod $POD_NAME has CPU usage above 30% for over 1 minute.\"
            },
            \"startsAt\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
            \"endsAt\": \"0001-01-01T00:00:00Z\",
            \"generatorURL\": \"http://prometheus:9090\",
            \"fingerprint\": \"test123\"
          }
        ]
      }" | python3 -m json.tool

    kill $PF_PID 2>/dev/null || true
    ok "Manual webhook sent. Check logs: kubectl logs deploy/postmortem-ai-service"
    ;;

  *)
    echo "Usage: $0 [cpu|crash|manual]"
    echo "  cpu    — enables CPU stress env var on the demo app"
    echo "  crash  — crashes a pod to cause restart loop"
    echo "  manual — sends a test webhook directly to the service"
    exit 1
    ;;
esac
