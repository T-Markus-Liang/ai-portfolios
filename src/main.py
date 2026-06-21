"""Daily incremental brief with multi-source fetch.

Source order (per handle):
  1. Nitter RSS (free, no key)  — primary
  2. twitterapi.io              — fallback if Nitter all fail

Both produce normalized tweets that share id/text/url/createdAt/createdAtTs.
Incremental window is enforced via data/last_seen.json.
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
STATE_PATH = DATA_DIR / "last_seen.json"

SH = ZoneInfo("Asia/Shanghai")

NEW_ACCOUNT_LOOKBACK_DAYS = 7
NEW_ACCOUNT_FETCH_COUNT = 100
TRACKED_FETCH_COUNT = 40

# Use package-style imports; main is launched via `python -m src.main`.
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))
    from src.state import load_state, save_state, update_handle  # type: ignore
    from src.sources.nitter import NitterError, fetch_user_rss  # type: ignore
    from src.sources.twitterapi_io import fetch_user_tweets as fetch_via_tio  # type: ignore
    from src.fetch_x_data import TwitterAPIError  # type: ignore
else:
    from .state import load_state, save_state, update_handle
    from .sources.nitter import NitterError, fetch_user_rss
    from .sources.twitterapi_io import fetch_user_tweets as fetch_via_tio
    from .fetch_x_data import TwitterAPIError


def _load_handles() -> list[str]:
    path = CONFIG_DIR / "kol_accounts.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [
        (item.get("handle") or "").strip()
        for item in (data.get("kol_accounts") or [])
        if (item.get("handle") or "").strip()
    ]


def _load_nitter_instances() -> list[str] | None:
    path = CONFIG_DIR / "sources.yaml"
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    instances = data.get("nitter_instances") or []
    return [s.strip() for s in instances if isinstance(s, str) and s.strip()] or None


def _allow_tio_fallback() -> bool:
    flag = (os.environ.get("ALLOW_TWITTERAPI_IO_FALLBACK") or "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    # Default: fall back only when the key is configured.
    return bool(os.environ.get("TWITTERAPI_IO_KEY"))


def _id_int(t: dict) -> int:
    try:
        return int(t.get("id") or 0)
    except (TypeError, ValueError):
        return 0


def _filter_incremental(tweets: list[dict], last_id: str | None) -> list[dict]:
    threshold = 0
    if last_id:
        try:
            threshold = int(last_id)
        except ValueError:
            threshold = 0
    out = [t for t in tweets if _id_int(t) > threshold]
    out.sort(key=_id_int)
    return out


def _filter_bootstrap(tweets: list[dict], cutoff_utc: dt.datetime) -> list[dict]:
    cutoff_ts = cutoff_utc.timestamp()
    out = []
    for t in tweets:
        ts = float(t.get("createdAtTs") or 0)
        if ts == 0.0:
            # We cannot date-filter when timestamp is missing (e.g. twitterapi.io);
            # keep all — caller will still cap by source-side `count`.
            out.append(t)
        elif ts >= cutoff_ts:
            out.append(t)
    out.sort(key=_id_int)
    return out


def _fmt_tweet(t: dict) -> str:
    text = (t.get("text") or "").replace("\n", " ").strip()
    if len(text) > 260:
        text = text[:260] + "…"
    created = t.get("createdAt", "")
    url = t.get("url") or ""
    likes = t.get("likeCount") or 0
    rts = t.get("retweetCount") or 0
    meta = f"  (♥{likes} / 🔁{rts})" if (likes or rts) else ""
    return f"  - [{created}] {text}{meta} {url}".rstrip()


def _fetch_one_handle(
    handle: str,
    nitter_instances: list[str] | None,
    fetch_count: int,
    allow_tio: bool,
) -> tuple[list[dict], str, list[str]]:
    """Return (tweets, used_source, errors_per_source)."""
    errors: list[str] = []
    try:
        tweets = fetch_user_rss(handle, instances=nitter_instances)
        if tweets:
            return tweets[:fetch_count], "nitter", errors
        errors.append("nitter: empty")
    except NitterError as exc:
        errors.append(f"nitter: {exc}")

    if not allow_tio:
        return [], "none", errors

    try:
        tweets = fetch_via_tio(handle, count=fetch_count)
        return tweets, "twitterapi.io", errors
    except TwitterAPIError as exc:
        errors.append(f"twitterapi.io: {exc}")
        return [], "none", errors


def _render_markdown(now_sh: dt.datetime, results: list[dict]) -> str:
    lines = [
        "# AI 基建与美股成长股日报",
        "",
        f"生成时间：{now_sh.strftime('%Y-%m-%d %H:%M')} Asia/Shanghai",
        "窗口：过去 24 小时（新账号回溯 7 天）",
        "数据源：Nitter RSS 优先，twitterapi.io 兜底",
        "",
        "## KOL 新增推文",
        "",
    ]
    total_new = 0
    if not results:
        lines.append("- 当前未配置任何 KOL handle，请在 `config/kol_accounts.yaml` 中补充。")
    else:
        for item in results:
            handle = item["handle"]
            mode = item["mode"]
            new_tweets = item.get("new_tweets") or []
            source = item.get("source") or "none"
            errors = item.get("errors") or []
            tag = "新账号 / 回溯 7 天" if mode == "bootstrap" else "增量"
            if not new_tweets and source == "none":
                err_summary = "; ".join(errors) or "no data"
                lines.append(f"- @{handle} : 抓取失败 ({err_summary})")
                continue
            total_new += len(new_tweets)
            lines.append(f"- @{handle} : 新增 {len(new_tweets)} 条（{tag}，来源 {source}）")
            for t in new_tweets:
                lines.append(_fmt_tweet(t))
    lines += [
        "",
        f"合计新增：{total_new} 条。",
        "",
        "## 备注",
        "",
        "- 链路打通版本，尚未接入 LLM 总结。",
        "- 下一阶段：去重已通过 last_seen 完成，将加入分类、情绪、个股关联、预警与中文总结。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    now_sh = dt.datetime.now(SH)
    now_utc = dt.datetime.now(dt.timezone.utc)
    bootstrap_cutoff = now_utc - dt.timedelta(days=NEW_ACCOUNT_LOOKBACK_DAYS)

    DATA_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    handles = _load_handles()
    nitter_instances = _load_nitter_instances()
    allow_tio = _allow_tio_fallback()

    state = load_state(STATE_PATH)
    results: list[dict] = []

    for handle in handles:
        record = state.get(handle) or {}
        last_id = record.get("last_tweet_id")
        mode = "incremental" if last_id else "bootstrap"
        fetch_count = TRACKED_FETCH_COUNT if last_id else NEW_ACCOUNT_FETCH_COUNT

        tweets, source, errors = _fetch_one_handle(
            handle, nitter_instances, fetch_count, allow_tio
        )

        if not tweets:
            results.append(
                {"handle": handle, "mode": mode, "new_tweets": [], "source": "none", "errors": errors}
            )
            continue

        if last_id:
            new_tweets = _filter_incremental(tweets, last_id)
        else:
            new_tweets = _filter_bootstrap(tweets, bootstrap_cutoff)

        if new_tweets:
            newest = str(max(_id_int(t) for t in new_tweets))
            if newest != "0":
                update_handle(state, handle, newest, now_sh.isoformat())
        elif not last_id and tweets:
            newest = str(max(_id_int(t) for t in tweets))
            if newest != "0":
                update_handle(state, handle, newest, now_sh.isoformat())

        results.append(
            {
                "handle": handle,
                "mode": mode,
                "new_tweets": new_tweets,
                "source": source,
                "errors": errors,
            }
        )

    save_state(STATE_PATH, state)

    raw_path = DATA_DIR / f"raw_{now_sh.strftime('%Y%m%d_%H%M')}.json"
    raw_path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    md = _render_markdown(now_sh, results)
    report_path = REPORTS_DIR / f"report_{now_sh.strftime('%Y%m%d')}.md"
    report_path.write_text(md, encoding="utf-8")

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"report_path={report_path.as_posix()}\n")

    print(f"[OK] report -> {report_path}")
    print(f"[OK] raw    -> {raw_path}")
    print(f"[OK] state  -> {STATE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
