#!/usr/bin/env bash
set -euo pipefail
url="${BASE_URL:-https://localhost}/hub/api"
for _ in $(seq 1 60); do
  if curl -ksf "$url" >/dev/null; then
    exit 0
  fi
  sleep 2
done
echo "hub not ready"
exit 1
