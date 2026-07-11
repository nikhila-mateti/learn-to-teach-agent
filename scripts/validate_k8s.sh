#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/k8s"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl not installed; skipping Kubernetes validation"
  exit 0
fi

echo "Running client-side dry-run validation"
for file in namespace.yaml app-configmap.yaml app-secret.example.yaml app-deployment.yaml app-service.yaml dev-postgres.yaml; do
  echo "Validating $file"
  kubectl apply --dry-run=client -f "$file"
done

echo "K8S VALIDATION PASSED"
