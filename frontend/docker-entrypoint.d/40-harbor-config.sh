#!/bin/sh
set -eu

cat > /usr/share/nginx/html/config.js <<EOF
window.__APP_CONFIG__ = {
  authRequired: "${HARBOR_AUTH_REQUIRED:-true}" === "true",
  cognitoUserPoolId: "${HARBOR_COGNITO_USER_POOL_ID:-}",
  cognitoClientId: "${HARBOR_COGNITO_CLIENT_ID:-}"
};
EOF
