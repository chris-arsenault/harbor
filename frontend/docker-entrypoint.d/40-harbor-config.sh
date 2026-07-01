#!/bin/sh
set -eu

CONFIG_PATH="${HARBOR_FRONTEND_CONFIG_PATH:-/usr/share/nginx/html/config.js}"
COGNITO_CLIENT_ID="${HARBOR_COGNITO_CLIENT_ID:-${HARBOR_AUTH_CLIENT_ID:-}}"
COGNITO_USER_POOL_ID="${HARBOR_COGNITO_USER_POOL_ID:-}"
AUTH_ISSUER_URL="${HARBOR_AUTH_ISSUER_URL:-}"

if [ -z "${COGNITO_USER_POOL_ID}" ] && [ -n "${AUTH_ISSUER_URL}" ]; then
  AUTH_ISSUER_URL="${AUTH_ISSUER_URL%/}"
  COGNITO_USER_POOL_ID="${AUTH_ISSUER_URL##*/}"
fi

cat > "${CONFIG_PATH}" <<EOF
window.__APP_CONFIG__ = {
  authRequired: "${HARBOR_AUTH_REQUIRED:-true}" === "true",
  cognitoUserPoolId: "${COGNITO_USER_POOL_ID}",
  cognitoClientId: "${COGNITO_CLIENT_ID}"
};
EOF
