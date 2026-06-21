"""Daily incremental brief with multi-source fetch + optional LLM summary.

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
SUMMARY_DIR = REPORTS_DIR / "summaries"
STATE_PATH = DATA_DIR / "last_seen.json"
REPORT_TITLE = "全球投资动能监控"
WECHAT_GROUP_ARCHIVE_DIR = DATA_DIR / "wechat_groups" / "archives"

SH = ZoneInfo("Asia/Shanghai")

NEW_ACCOUNT_LOOKBACK_DAYS = 7
NEW_ACCOUNT_FETCH_COUNT = 100
TRACKED_FETCH_COUNT = 40

# Use package-style imports; main is launched via `python -m src.main`.
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))
    from src.state import load_state, save_state, update_handle  # type: ignore
    from src.sources.nitter import NitterError, fetch_user_rss  # type: ignore
    from src.sources.rss_articles import build_manual_articles, fetch_articles  # type: ignore
    from src.sources.twitterapi_io import fetch_user_tweets as fetch_via_tio  # type: ignore
    from src.sources.wechat_groups import load_wechat_group_archives  # type: ignore
    from src.fetch_x_data import TwitterAPIError  # type: ignore
    from src.summarize import LLMError, summarize  # type: ignore
else:
    from .state import load_state, save_state, update_handle
    from .sources.nitter import NitterError, fetch_user_rss
    from .sources.rss_articles import build_manual_articles, fetch_articles
    from .sources.twitterapi_io import fetch_user_tweets as fetch_via_tio
    from .sources.wechat_groups import load_wechat_group_archives
    from .fetch_x_data import TwitterAPIError
    from .summarize import LLMError, summarize


def _load_kol_accounts() -> list[dict[str, str]]:
    path = CONFIG_DIR / "kol_accounts.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    accounts: list[dict[str, str]] = []
    for item in data.get("kol_accounts") or []:
        handle = (item.get("handle") or "").strip()
        if not handle:
            continue
        name = (item.get("name") or handle).strip()
        accounts.append({"name": name, "handle": handle})
    return accounts


def _load_nitter_instances() -> list[str] | None:
    path = CONFIG_DIR / "sources.yaml"
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    instances = data.get("nitter_instances") or []
    return [s.strip() for s in instances if isinstance(s, str) and s.strip()] or None


def _load_article_sources() -> list[dict]:
    path = CONFIG_DIR / "article_sources.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources: list[dict] = []
    for item in data.get("article_sources") or []:
        if not item.get("enabled"):
            continue
        if item.get("local_only") and os.environ.get("GITHUB_ACTIONS"):
            continue
        if not (item.get("rss_url") or "").strip() and not (item.get("manual_articles") or []):
            continue
        sources.append(dict(item))
    return sources


def _wechat_groups_enabled() -> bool:
    path = CONFIG_DIR / "wechat_groups.yaml"
    if not path.exists():
        return False
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for item in data.get("wechat_groups") or []:
        if item.get("enabled") and item.get("include_in_report", True):
            return True
    return False


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


def _item_sort_key(item: dict) -> tuple[float, int]:
    return (float(item.get("createdAtTs") or 0), _id_int(item))


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
    except Exception as exc:
        errors.append(f"nitter: {type(exc).__name__}: {exc}")

    if not allow_tio:
        return [], "none", errors

    try:
        tweets = fetch_via_tio(handle, count=fetch_count)
        return tweets, "twitterapi.io", errors
    except Exception as exc:
        errors.append(f"twitterapi.io: {type(exc).__name__}: {exc}")
        return [], "none", errors


def _filter_articles(articles: list[dict], last_id: str | None, cutoff_utc: dt.datetime) -> list[dict]:
    cutoff_ts = cutoff_utc.timestamp()
    out: list[dict] = []
    seen_last = not last_id
    sorted_articles = sorted(articles, key=_item_sort_key)
    if last_id and all(str(article.get("id") or "") != last_id for article in sorted_articles):
        seen_last = True
    for article in sorted_articles:
        article_id = str(article.get("id") or "")
        ts = float(article.get("createdAtTs") or 0)
        if not seen_last:
            if article_id == last_id:
                seen_last = True
            continue
        if ts == 0.0 or ts >= cutoff_ts:
            out.append(article)
    return out


def _fetch_article_sources(sources: list[dict], state: dict, cutoff_utc: dt.datetime, now_iso: str, force_days: int) -> list[dict]:
    results: list[dict] = []
    for source_config in sources:
        name = (source_config.get("name") or "").strip()
        source_id = f"article:{source_config.get('kind') or 'article'}:{name}"
        errors: list[str] = []
        articles: list[dict] = []
        try:
            articles.extend(fetch_articles(source_config))
        except Exception as exc:
            errors.append(f"rss: {type(exc).__name__}: {exc}")
        seen_urls = {article.get("url") for article in articles if article.get("url")}
        for article in build_manual_articles(source_config):
            if article.get("url") not in seen_urls:
                articles.append(article)
                seen_urls.add(article.get("url"))

        if not articles:
            results.append(
                {
                    "name": name,
                    "handle": source_id,
                    "mode": "article",
                    "new_tweets": [],
                    "source": "none",
                    "errors": errors,
                }
            )
            continue

        last_id = None if force_days else (state.get(source_id) or {}).get("last_tweet_id")
        new_articles = _filter_articles(articles, last_id, cutoff_utc)
        if not force_days and articles:
            newest = str(max(articles, key=_item_sort_key).get("id") or "")
            if newest:
                update_handle(state, source_id, newest, now_iso)
        results.append(
            {
                "name": name,
                "handle": source_id,
                "mode": "article_rss",
                "new_tweets": new_articles,
                "source": f"article:{source_config.get('kind') or 'article'}",
                "errors": errors,
            }
        )
    return results


def _fetch_wechat_group_archives(state: dict, cutoff_utc: dt.datetime, now_iso: str, force_days: int) -> list[dict]:
    if not _wechat_groups_enabled():
        return []
    archives = load_wechat_group_archives(WECHAT_GROUP_ARCHIVE_DIR)
    if not archives:
        return []
    source_id = "wechat_group:archives"
    last_id = None if force_days else (state.get(source_id) or {}).get("last_tweet_id")
    new_archives = _filter_articles(archives, last_id, cutoff_utc)
    if not force_days and archives:
        newest = str(max(archives, key=_item_sort_key).get("id") or "")
        if newest:
            update_handle(state, source_id, newest, now_iso)
    return [
        {
            "name": "微信投资群原文",
            "handle": source_id,
            "mode": "article_rss",
            "new_tweets": new_archives,
            "source": "wechat_group:local",
            "errors": [],
        }
    ]


def _render_raw_markdown(now_sh: dt.datetime, results: list[dict], llm_error: str | None = None) -> str:
    lines = [
        f"# {REPORT_TITLE}（原文模式）" if llm_error else f"# {REPORT_TITLE}",
        "",
        f"生成时间：{now_sh.strftime('%Y-%m-%d %H:%M')} Asia/Shanghai",
        "窗口：过去 24 小时（新账号回溯 7 天）",
        "数据源：Nitter RSS 优先，twitterapi.io 兜底；文章源支持 RSS/Atom；本地微信投资群摘要",
        "",
    ]
    if llm_error:
        lines += [f"> ⚠️ LLM 调用失败，退回原文模式：{llm_error}", ""]
    lines += [
        "## 新增内容",
        "",
    ]
    total_new = 0
    if not results:
        lines.append("- 当前未配置任何 KOL handle，请在 `config/kol_accounts.yaml` 中补充。")
    else:
        for item in results:
            name = item.get("name") or item["handle"]
            handle = item["handle"]
            mode = item["mode"]
            new_tweets = item.get("new_tweets") or []
            source = item.get("source") or "none"
            errors = item.get("errors") or []
            tag = "文章 RSS" if mode == "article_rss" else ("新账号 / 回溯 7 天" if mode == "bootstrap" else "增量")
            if not new_tweets and source == "none":
                err_summary = "; ".join(errors) or "no data"
                lines.append(f"- @{handle} : 抓取失败 ({err_summary})")
                continue
            total_new += len(new_tweets)
            label = name if mode == "article_rss" else f"{name}（@{handle}）"
            lines.append(f"- {label}: 新增 {len(new_tweets)} 条（{tag}，来源 {source}）")
            for t in new_tweets:
                lines.append(_fmt_tweet(t))
    lines += [
        "",
        f"合计新增：{total_new} 条。",
        "",
    ]
    return "\n".join(lines)


def _source_counts(results: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in results:
        source = item.get("source") or "none"
        if item.get("new_tweets"):
            counts[source] = counts.get(source, 0) + 1
    return counts


def _flatten_new_tweets(results: list[dict]) -> list[dict]:
    flat: list[dict] = []
    for item in results:
        handle = item["handle"]
        name = item.get("name") or handle
        is_article = str(item.get("mode") or "").startswith("article")
        kol_label = name if is_article else (f"{name}（@{handle}）" if name and name != handle else f"@{handle}")
        for tweet in item.get("new_tweets") or []:
            enriched = dict(tweet)
            enriched["kol"] = kol_label
            enriched["name"] = name
            enriched["handle"] = handle
            enriched["contentType"] = enriched.get("contentType") or ("article" if is_article else "tweet")
            flat.append(enriched)
    return flat


def _build_discord_title(source_counts: dict[str, int], total_new: int, llm_failed: bool) -> str:
    source_summary = " / ".join(f"{key}:{value}" for key, value in sorted(source_counts.items())) or "none"
    title = f"{REPORT_TITLE} · {source_summary} · {total_new} 新"
    if llm_failed:
        title += " · llm-failed"
    return title


def _date_ymd(now_sh: dt.datetime) -> str:
    return now_sh.strftime("%Y%m%d")


def _cn_digits(value: int, width: int | None = None) -> str:
    digits = "零一二三四五六七八九"
    text = f"{value:0{width}d}" if width else str(value)
    return "".join(digits[int(ch)] for ch in text)


def _cn_number(value: int) -> str:
    if value < 10:
        return _cn_digits(value)
    if value == 10:
        return "十"
    if value < 20:
        return "十" + _cn_digits(value % 10)
    tens, ones = divmod(value, 10)
    return _cn_digits(tens) + "十" + (_cn_digits(ones) if ones else "")


def _cn_date(now_sh: dt.datetime) -> str:
    return f"{_cn_digits(now_sh.year)}年{_cn_number(now_sh.month)}月{_cn_number(now_sh.day)}日"


def _cn_datetime(now_sh: dt.datetime) -> str:
    return f"{_cn_date(now_sh)}{_cn_number(now_sh.hour)}时{_cn_digits(now_sh.minute, 2)}分"


def _report_path(now_sh: dt.datetime) -> Path:
    return REPORTS_DIR / f"{REPORT_TITLE}{_cn_date(now_sh)}.md"


def _summary_archive_path(now_sh: dt.datetime) -> Path:
    return SUMMARY_DIR / f"{_cn_datetime(now_sh)}{REPORT_TITLE}.md"


def _force_lookback_days() -> int:
    raw = (os.environ.get("FORCE_LOOKBACK_DAYS") or "0").strip()
    try:
        value = int(raw)
    except ValueError:
        return 0
    return max(0, min(value, 30))


def _render_summary_markdown(
    now_sh: dt.datetime,
    summary_md: str,
    results: list[dict],
    source_counts: dict[str, int],
    total_new: int,
) -> str:
    source_summary = " / ".join(f"{key}:{value}" for key, value in sorted(source_counts.items())) or "none"
    lines = [
        f"# {REPORT_TITLE}",
        "",
        f"生成时间：{now_sh.strftime('%Y-%m-%d %H:%M')} Asia/Shanghai",
        "窗口：过去 24 小时（新账号回溯 7 天）",
        f"数据源：{source_summary}",
        f"新增内容：{total_new} 条",
        f"模型：{(os.environ.get('ARK_MODEL') or 'kimi-k2.6').strip()}",
        "",
        summary_md.strip(),
        "",
    ]
    return "\n".join(lines)


def _write_summary_archive(now_sh: dt.datetime, report_md: str, total_new: int, source_counts: dict[str, int]) -> Path:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    source_summary = ", ".join(f"{key}:{value}" for key, value in sorted(source_counts.items())) or "none"
    path = _summary_archive_path(now_sh)
    front_matter = "\n".join(
        [
            "---",
            f"date: {now_sh.isoformat()}",
            f"total_new: {total_new}",
            f"sources: \"{source_summary}\"",
            "---",
            "",
        ]
    )
    path.write_text(front_matter + report_md, encoding="utf-8")
    return path


def main() -> int:
    now_sh = dt.datetime.now(SH)
    now_utc = dt.datetime.now(dt.timezone.utc)
    force_days = _force_lookback_days()
    lookback_days = force_days or NEW_ACCOUNT_LOOKBACK_DAYS
    bootstrap_cutoff = now_utc - dt.timedelta(days=lookback_days)

    DATA_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    accounts = _load_kol_accounts()
    article_sources = _load_article_sources()
    nitter_instances = _load_nitter_instances()
    allow_tio = _allow_tio_fallback()

    state = load_state(STATE_PATH)
    results: list[dict] = []

    for account in accounts:
        handle = account["handle"]
        name = account["name"]
        record = state.get(handle) or {}
        last_id = None if force_days else record.get("last_tweet_id")
        mode = "force_bootstrap" if force_days else ("incremental" if last_id else "bootstrap")
        fetch_count = NEW_ACCOUNT_FETCH_COUNT if not last_id else TRACKED_FETCH_COUNT

        tweets, source, errors = _fetch_one_handle(
            handle, nitter_instances, fetch_count, allow_tio
        )

        if not tweets:
            results.append(
                {"name": name, "handle": handle, "mode": mode, "new_tweets": [], "source": "none", "errors": errors}
            )
            continue

        if last_id:
            new_tweets = _filter_incremental(tweets, last_id)
        else:
            new_tweets = _filter_bootstrap(tweets, bootstrap_cutoff)

        if force_days:
            pass
        elif new_tweets:
            newest = str(max(_id_int(t) for t in new_tweets))
            if newest != "0":
                update_handle(state, handle, newest, now_sh.isoformat())
        elif not last_id and tweets:
            newest = str(max(_id_int(t) for t in tweets))
            if newest != "0":
                update_handle(state, handle, newest, now_sh.isoformat())

        results.append(
            {
                "name": name,
                "handle": handle,
                "mode": mode,
                "new_tweets": new_tweets,
                "source": source,
                "errors": errors,
            }
        )

    results.extend(_fetch_article_sources(article_sources, state, bootstrap_cutoff, now_sh.isoformat(), force_days))
    results.extend(_fetch_wechat_group_archives(state, bootstrap_cutoff, now_sh.isoformat(), force_days))

    if not force_days:
        save_state(STATE_PATH, state)

    raw_path = DATA_DIR / f"raw_{now_sh.strftime('%Y%m%d_%H%M')}.json"
    raw_path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    source_counts = _source_counts(results)
    flat_new_tweets = _flatten_new_tweets(results)
    total_new = len(flat_new_tweets)
    llm_failed = False
    llm_error = ""
    summary_md = ""

    if flat_new_tweets:
        try:
            summary_md = summarize(flat_new_tweets)
        except LLMError as exc:
            llm_failed = True
            llm_error = str(exc)

    if summary_md:
        md = _render_summary_markdown(now_sh, summary_md, results, source_counts, total_new)
    elif total_new == 0:
        md = "\n".join(
            [
                f"# {REPORT_TITLE}",
                "",
                f"生成时间：{now_sh.strftime('%Y-%m-%d %H:%M')} Asia/Shanghai",
                "窗口：过去 24 小时（新账号回溯 7 天）",
                f"数据源：{' / '.join(f'{k}:{v}' for k, v in sorted(source_counts.items())) or 'none'}",
                "",
                "今日所有追踪 KOL / 文章源 / 微信投资群均无新增内容，跳过 LLM 总结。",
                "",
            ]
        )
    else:
        md = _render_raw_markdown(now_sh, results, llm_error)

    report_path = _report_path(now_sh)
    report_path.write_text(md, encoding="utf-8")
    summary_path = _write_summary_archive(now_sh, md, total_new, source_counts)

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"report_path={report_path.as_posix()}\n")
            fh.write(f"summary_path={summary_path.as_posix()}\n")
            fh.write(
                f"discord_title={_build_discord_title(source_counts, total_new, llm_failed)}\n"
            )

    print(f"[OK] report -> {report_path}")
    print(f"[OK] summary -> {summary_path}")
    print(f"[OK] raw    -> {raw_path}")
    print(f"[OK] state  -> {STATE_PATH}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
