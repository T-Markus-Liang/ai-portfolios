"""MVP entrypoint: fetch -> minimal markdown report -> save under reports/.

This stage does NOT call an LLM. It only verifies the pipeline:
twitterapi.io -> local markdown -> Discord push (handled by workflow).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"

SH = ZoneInfo("Asia/Shanghai")


def _decide_report_type(now_sh: dt.datetime) -> str:
    env = os.environ.get("REPORT_TYPE", "auto").strip().lower()
    if env in {"morning", "evening"}:
        return env
    return "morning" if now_sh.hour < 14 else "evening"


def _load_handles() -> list[str]:
    path = CONFIG_DIR / "kol_accounts.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    handles = []
    for item in data.get("kol_accounts", []) or []:
        handle = (item.get("handle") or "").strip()
        if handle:
            handles.append(handle)
    return handles


def _render_markdown(report_type: str, now_sh: dt.datetime, fetched: list[dict]) -> str:
    title = "早报" if report_type == "morning" else "晚报"
    lines = [
        f"# AI 基建与美股成长股{title}",
        "",
        f"生成时间：{now_sh.strftime('%Y-%m-%d %H:%M')} Asia/Shanghai",
        f"模式：{report_type}",
        "",
        "## KOL 抓取概况",
        "",
    ]
    if not fetched:
        lines.append("- 当前未配置任何 KOL handle，请在 `config/kol_accounts.yaml` 中补充。")
    else:
        for item in fetched:
            handle = item.get("handle")
            if "error" in item:
                lines.append(f"- @{handle} : 抓取失败 ({item['error']})")
                continue
            data = item.get("data") or {}
            tweets = data.get("tweets") or data.get("data") or []
            count = len(tweets) if isinstance(tweets, list) else "?"
            lines.append(f"- @{handle} : 抓到 {count} 条")
    lines += [
        "",
        "## 备注",
        "",
        "- 这是链路打通版本，尚未接入 LLM 总结。",
        "- 下一阶段会加入去重、分类、情绪、预警与中文简报生成。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    now_sh = dt.datetime.now(SH)
    report_type = _decide_report_type(now_sh)

    DATA_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    handles = _load_handles()

    fetched: list[dict] = []
    if handles:
        try:
            from .fetch_x_data import fetch_kol_recent
        except ImportError:
            sys.path.insert(0, str(ROOT))
            from src.fetch_x_data import fetch_kol_recent  # type: ignore
        fetched = fetch_kol_recent(handles, count_per_user=5)

    raw_path = DATA_DIR / f"raw_{now_sh.strftime('%Y%m%d_%H%M')}_{report_type}.json"
    raw_path.write_text(json.dumps(fetched, ensure_ascii=False, indent=2), encoding="utf-8")

    md = _render_markdown(report_type, now_sh, fetched)
    report_path = REPORTS_DIR / f"report_{now_sh.strftime('%Y%m%d')}_{report_type}.md"
    report_path.write_text(md, encoding="utf-8")

    # Expose path for the workflow's next step (Discord push).
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"report_path={report_path.as_posix()}\n")
            fh.write(f"report_type={report_type}\n")

    print(f"[OK] report -> {report_path}")
    print(f"[OK] raw    -> {raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
