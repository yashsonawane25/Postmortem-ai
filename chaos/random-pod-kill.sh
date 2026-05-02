#!/usr/bin/env bash
# =============================================================================
# ChaosGuard - Random Pod Kill
# =============================================================================
set -euo pipefail

API_URL="http://localhost:8000"
EXPERIMENT_ID=$(uuidgen | tr '[:upper:]' '[:lower:]' | head -c 8)

echo "[INFO] Registering chaos experiment: $EXPERIMENT_ID"
curl -s -X POST "$API_URL/chaos/register" \
  -H "Content-Type: application/json" \
  -d "{\"experiment_id\": \"$EXPERIMENT_ID\", \"target_pod\": \"demo-broken-app\"}"

echo ""
echo "[INFO] Finding a target pod..."
TARGET_POD=$(kubectl get pods -l app=demo-broken-app -o jsonpath='{.items[0].metadata.name}')

if [ -z "$TARGET_POD" ]; then
    echo "[ERROR] No pod found for demo-broken-app!"
    exit 1
fi

echo "[INFO] Killing pod: $TARGET_POD"
kubectl delete pod "$TARGET_POD" --wait=false

echo "[INFO] Waiting 5 seconds for SLO checker or fallback..."
sleep 5

echo "[INFO] Triggering fallback alert to guarantee AI flow..."
# This matches the payload expected by Alertmanager
# We pass chaos_experiment=true to indicate it was from ChaosGuard
curl -s -X POST "$API_URL/alert" \
  -H "Content-Type: application/json" \
  -d "{
    \"version\": \"4\",
    \"groupKey\": \"chaos-group\",
    \"status\": \"firing\",
    \"receiver\": \"postmortem-ai\",
    \"alerts\": [
      {
        \"status\": \"firing\",
        \"labels\": {
          \"alertname\": \"ChaosExperimentSLOBreach\",
          \"namespace\": \"default\",
          \"pod\": \"$TARGET_POD\",
          \"severity\": \"CRITICAL\",
          \"chaos_experiment\": \"true\"
        },
        \"annotations\": {
          \"summary\": \"Chaos experiment caused an SLO breach\",
          \"description\": \"Pod $TARGET_POD became unavailable during the chaos experiment.\"
        },
        \"startsAt\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
        \"endsAt\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
      }
    ]
  }" > /dev/null

echo "[INFO] Updating chaos experiment status..."
curl -s -X POST "$API_URL/chaos/update" \
  -H "Content-Type: application/json" \
  -d "{\"experiment_id\": \"$EXPERIMENT_ID\", \"status\": \"COMPLETED\"}" > /dev/null

echo ""
echo "[OK] Chaos experiment $EXPERIMENT_ID completed and fallback alert fired."
