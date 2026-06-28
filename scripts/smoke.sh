#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${HARBOR_BASE_URL:-http://192.168.66.3:30091}"
EXPECTED_GIT_SHA="${EXPECTED_GIT_SHA:-}"
HARBOR_SMOKE_ACCESS_TOKEN="${HARBOR_SMOKE_ACCESS_TOKEN:-}"
SMOKE_TIMEOUT_SECONDS="${SMOKE_TIMEOUT_SECONDS:-900}"
SMOKE_POLL_SECONDS="${SMOKE_POLL_SECONDS:-10}"

VERSION_JSON=""
OBSERVED_GIT_SHA="unknown"
HTTP_CHECKED=false

require_jq() {
  if ! command -v jq >/dev/null 2>&1; then
    printf '%s\n' "scripts/smoke.sh requires jq to verify /version." >&2
    exit 1
  fi
}

fetch_version() {
  curl -fsS "${BASE_URL}/version"
}

extract_git_sha() {
  printf '%s\n' "$1" | jq -r '.git_sha // "unknown"'
}

version_matches_expected() {
  printf '%s\n' "$1" | jq -e --arg expected "${EXPECTED_GIT_SHA}" '.git_sha == $expected' >/dev/null
}

check_static_config() {
  grep -q 'proxy_set_header Upgrade $http_upgrade' "${ROOT_DIR}/frontend/nginx.conf"
  grep -q 'proxy_set_header Connection "upgrade"' "${ROOT_DIR}/frontend/nginx.conf"
  grep -q 'include /etc/nginx/mime.types' "${ROOT_DIR}/frontend/nginx.conf"
  grep -q 'proxy_read_timeout 10m' "${ROOT_DIR}/frontend/nginx.conf"
  grep -q 'location = /version' "${ROOT_DIR}/frontend/nginx.conf"
  grep -q '/config.js' "${ROOT_DIR}/frontend/index.html"
  grep -q '192.168.66.3:30091' "${ROOT_DIR}/compose.yaml"
}

check_http_smoke() {
  curl -fsS "${BASE_URL}/health" >/dev/null
  curl -fsS "${BASE_URL}/ready" >/dev/null
  check_api_auth

  INDEX_HTML="$(curl -fsS "${BASE_URL}/")"
  ASSET_PATH="$(
    printf '%s\n' "${INDEX_HTML}" \
      | grep -oE 'src="/assets/[^"]+\.js"' \
      | head -n 1 \
      | cut -d '"' -f 2
  )"
  test -n "${ASSET_PATH}"
  curl -fsSI "${BASE_URL}${ASSET_PATH}" | grep -qi '^Content-Type: application/javascript'
  HTTP_CHECKED=true
}

check_api_auth() {
  local status_code

  if [ -n "${HARBOR_SMOKE_ACCESS_TOKEN}" ]; then
    curl -fsS \
      -H "Authorization: Bearer ${HARBOR_SMOKE_ACCESS_TOKEN}" \
      "${BASE_URL}/api/status" \
      | jq -e 'has("mode")' >/dev/null
    return
  fi

  status_code="$(curl -sS -o /dev/null -w '%{http_code}' "${BASE_URL}/api/status")"
  if [ "${status_code}" != "401" ]; then
    printf '%s\n' "Expected /api/status to require auth, got HTTP ${status_code}." >&2
    return 1
  fi
}

wait_for_expected_git_sha() {
  local deadline=$((SECONDS + SMOKE_TIMEOUT_SECONDS))
  local version_json=""
  local observed="unavailable"

  while true; do
    if version_json="$(fetch_version 2>/dev/null)"; then
      observed="$(extract_git_sha "${version_json}" 2>/dev/null || printf '%s' "unavailable")"
      if version_matches_expected "${version_json}"; then
        VERSION_JSON="${version_json}"
        OBSERVED_GIT_SHA="${observed}"
        return 0
      fi
    fi

    if ((SECONDS >= deadline)); then
      printf '%s\n' "Timed out waiting for expected commit ${EXPECTED_GIT_SHA}." >&2
      printf '%s\n' "Last observed commit: ${observed}." >&2
      return 1
    fi

    sleep "${SMOKE_POLL_SECONDS}"
  done
}

check_expected_git_sha_once() {
  VERSION_JSON="$(fetch_version)"
  OBSERVED_GIT_SHA="$(extract_git_sha "${VERSION_JSON}")"
  check_http_smoke
  if ! version_matches_expected "${VERSION_JSON}"; then
    printf '%s\n' \
      "Harbor endpoint is healthy, but running commit ${OBSERVED_GIT_SHA} != expected ${EXPECTED_GIT_SHA}." \
      >&2
    printf '%s\n' "Deployment may still be in progress." >&2
    return 1
  fi
}

require_jq
check_static_config

if [ -n "${EXPECTED_GIT_SHA}" ]; then
  if ((SMOKE_TIMEOUT_SECONDS <= 0)); then
    check_expected_git_sha_once
  else
    wait_for_expected_git_sha
  fi
fi

if [ -z "${VERSION_JSON}" ]; then
  VERSION_JSON="$(fetch_version)"
  OBSERVED_GIT_SHA="$(extract_git_sha "${VERSION_JSON}")"
fi

if [ "${HTTP_CHECKED}" = false ]; then
  check_http_smoke
fi

printf '%s\n' "Harbor deployed commit ${OBSERVED_GIT_SHA} and passed smoke checks."
