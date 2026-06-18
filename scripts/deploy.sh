#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${ROOT_DIR}"

make ci
docker compose config >/dev/null
bash -n scripts/smoke.sh

printf '%s\n' "Deploy through Ahara shared CI/Komodo by pushing main."
printf '%s\n' "Credentialed manual deploy or smoke commands must use with-cred -- <command>."
