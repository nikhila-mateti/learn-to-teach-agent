#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Checking containers"
app_status="$(docker compose ps --status running --services | grep -E '^app$' || true)"
db_status="$(docker compose ps --status running --services | grep -E '^db$' || true)"

if [[ -z "$app_status" ]]; then
  echo "FAIL: app container is not running"
  exit 1
fi
echo "OK: app container running"

if [[ -z "$db_status" ]]; then
  echo "FAIL: db container is not running"
  exit 1
fi
echo "OK: db container running"

db_health="$(docker inspect --format='{{.State.Health.Status}}' "$(docker compose ps -q db)")"
if [[ "$db_health" != "healthy" ]]; then
  echo "FAIL: db health is $db_health"
  exit 1
fi
echo "OK: db healthy ($db_health)"

echo "==> Hitting health endpoints"
live_code="$(curl -s -o /tmp/lta_live.json -w '%{http_code}' http://localhost:8000/health/live)"
ready_code="$(curl -s -o /tmp/lta_ready.json -w '%{http_code}' http://localhost:8000/health/ready)"
home_code="$(curl -s -o /tmp/lta_home.html -w '%{http_code}' http://localhost:8000/)"

echo "GET /health/live -> $live_code $(cat /tmp/lta_live.json)"
echo "GET /health/ready -> $ready_code $(cat /tmp/lta_ready.json)"
echo "GET / -> $home_code"

if [[ "$live_code" != "200" || "$ready_code" != "200" || "$home_code" != "200" ]]; then
  echo "FAIL: smoke HTTP checks"
  exit 1
fi

echo "SMOKE TEST PASSED"
