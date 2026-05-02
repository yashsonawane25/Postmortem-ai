#!/bin/bash
set -e

echo "🚀 Installing LitmusChaos via Helm..."

# Add Litmus Helm repository
helm repo add litmuschaos https://litmuschaos.github.io/litmus-helm/
helm repo update

# Create Litmus namespace
kubectl create namespace litmus || true

# Install LitmusChaos
helm install chaos litmuschaos/litmus \
  --namespace litmus \
  --set portal.frontend.service.type=NodePort

echo "✅ LitmusChaos installed successfully!"
echo "Check the pods using: kubectl get pods -n litmus"
echo "You can port-forward the frontend to view the UI:"
echo "kubectl port-forward svc/chaos-litmus-frontend 9091:9091 -n litmus"
