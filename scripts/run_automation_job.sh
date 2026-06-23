#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_PATH="$ROOT/docs/automation-runs.md"
TMP_DIR="${TMPDIR:-/tmp}/ai-portfolios-automation"
mkdir -p "$TMP_DIR" "$ROOT/docs"

JOB="${1:-}"
shift || true

case "$JOB" in
  wechat_articles)
    TITLE="微信公众号文章本地同步"
    CMD=("$ROOT/scripts/run_wechat_sync.sh" "$@")
    ;;
  wechat_group)
    TITLE="微信群原文归档本地同步"
    CMD=("$ROOT/scripts/run_wechat_group_sync.sh" "$@")
    ;;
  *)
    echo "Usage: $0 {wechat_articles|wechat_group} [args...]" >&2
    exit 2
    ;;
esac

cd "$ROOT"
START_ISO="$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S %Z')"
STAMP="$(date '+%Y%m%d_%H%M%S')"
OUT="$TMP_DIR/${JOB}_${STAMP}.out"
ERR="$TMP_DIR/${JOB}_${STAMP}.err"

if [[ ! -f "$LOG_PATH" ]]; then
  cat > "$LOG_PATH" <<'MD'
# 自动化运行台账

记录 Codex 本地自动化任务的执行结果。最新记录在最上方。

| 时间 | 任务 | 状态 | 摘要 |
|---|---|---|---|
MD
fi

"${CMD[@]}" >"$OUT" 2>"$ERR"
CODE=$?

if [[ "$CODE" -eq 0 ]]; then
  STATUS="成功"
else
  STATUS="失败($CODE)"
fi

SUMMARY="$({ tail -n 8 "$OUT"; tail -n 8 "$ERR"; } | tr '\n' ' ' | sed 's/|/／/g; s/[[:space:]][[:space:]]*/ /g; s/^ *//; s/ *$//')"
if [[ -z "$SUMMARY" ]]; then
  SUMMARY="无输出"
fi
if [[ ${#SUMMARY} -gt 360 ]]; then
  SUMMARY="${SUMMARY:0:360}…"
fi

python3 - "$LOG_PATH" "$START_ISO" "$TITLE" "$STATUS" "$SUMMARY" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
row = f"| {sys.argv[2]} | {sys.argv[3]} | {sys.argv[4]} | {sys.argv[5]} |\n"
text = path.read_text(encoding="utf-8")
marker = "|---|---|---|---|\n"
if marker in text:
    text = text.replace(marker, marker + row, 1)
else:
    text += "\n" + row
path.write_text(text, encoding="utf-8")
PY

cat "$OUT"
cat "$ERR" >&2
printf '\n[automation-log] %s %s -> %s\n' "$TITLE" "$STATUS" "$LOG_PATH"

if [[ "${NO_GIT:-0}" != "1" ]]; then
  git add docs/automation-runs.md
  if ! git diff --cached --quiet; then
    git commit -m "chore(automation): record local sync run [skip ci]"
    git push origin main
  fi
fi

exit "$CODE"
