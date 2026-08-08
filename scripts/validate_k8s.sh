#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/k8s"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl not installed; skipping Kubernetes validation"
  exit 0
fi

# kubectl's client dry-run still downloads the cluster's OpenAPI schema. Treat a
# missing local cluster as an explicit skip instead of failing an otherwise valid
# local setup with a connection-refused error.
if ! kubectl version --request-timeout=2s >/dev/null 2>&1; then
  echo "kubectl installed, but no Kubernetes API server is reachable; skipping schema validation"
  exit 0
fi

echo "Running client-side dry-run validation"
for file in namespace.yaml app-configmap.yaml app-secret.example.yaml app-deployment.yaml app-service.yaml dev-postgres.yaml; do
  echo "Validating $file"
  kubectl apply --dry-run=client -f "$file"
done

echo "K8S VALIDATION PASSED"
