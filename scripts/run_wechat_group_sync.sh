#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GROUP_NAME="${GROUP_NAME:-🈲言-2六便士AI吟诗}"

cd "$ROOT"

PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

"$PYTHON" scripts/capture_wechat_group_visible.py "$GROUP_NAME"
"$PYTHON" scripts/process_wechat_group_inbox.py

if [[ "${NO_GIT:-0}" == "1" ]]; then
  exit 0
fi

git add data/wechat_groups/archives/
if ! git diff --cached --quiet; then
  git commit -m "chore(wechat): sync group raw archive [skip ci]"
  git push origin main
else
  echo "[OK] no group archive changes to commit"
fi
