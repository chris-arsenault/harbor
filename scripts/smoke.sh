#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${HARBOR_BASE_URL:-http://192.168.66.3:30091}"

curl -fsS "${BASE_URL}/health" >/dev/null
curl -fsS "${BASE_URL}/ready" >/dev/null
curl -fsS "${BASE_URL}/api/status" | grep -q '"mode"'

grep -q 'proxy_set_header Upgrade $http_upgrade' "${ROOT_DIR}/frontend/nginx.conf"
grep -q 'proxy_set_header Connection "upgrade"' "${ROOT_DIR}/frontend/nginx.conf"
grep -q '192.168.66.3:30091' "${ROOT_DIR}/compose.yaml"

printf '%s\n' "Harbor smoke checks passed for ${BASE_URL}"
