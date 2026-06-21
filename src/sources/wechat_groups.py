"""Local WeChat group raw archive source."""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from pathlib import Path


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text.strip()
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text.strip()
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"')
    return meta, text[end + 5 :].strip()


def _parse_ts(value: str) -> float:
    value = (value or "").strip()
    if not value:
        return 0.0
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        pass
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp()
    except ValueError:
        return 0.0


def _title_from_body(body: str, fallback: str) -> str:
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return re.sub(r"^#+\s*", "", line).strip() or fallback
    return fallback


def load_wechat_group_archives(archive_dir: Path) -> list[dict]:
    if not archive_dir.exists():
        return []
    articles: list[dict] = []
    for path in sorted(archive_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        if not body:
            continue
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
        created = meta.get("date") or meta.get("generated_at") or ""
        title = meta.get("title") or _title_from_body(body, path.stem)
        articles.append(
            {
                "id": f"wechat_group:{path.stem}:{digest[:12]}",
                "text": body,
                "url": path.as_posix(),
                "createdAt": created,
                "createdAtTs": _parse_ts(created),
                "source": "local:wechat_group",
                "contentType": "wechat_group_archive",
                "sourceName": "微信投资群",
                "title": title,
            }
        )
    return articles


def load_wechat_group_summaries(summary_dir: Path) -> list[dict]:
    return load_wechat_group_archives(summary_dir)
