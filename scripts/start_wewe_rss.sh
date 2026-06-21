#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="$ROOT_DIR/docker/wewe-rss"

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon is not running. Please start Docker Desktop first." >&2
  exit 1
fi

cd "$COMPOSE_DIR"
docker compose up -d

echo "WeWe RSS is starting: http://127.0.0.1:4010"
echo "Auth code: ${WEWE_RSS_AUTH_CODE:-ai-portfolios}"
echo "Next: scan WeChat Reading account, then add official-account share links."
