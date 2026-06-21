"""Archive local WeChat group inbox messages as raw report inputs."""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
INBOX_DIR = ROOT / "data" / "wechat_groups" / "inbox"
PROCESSED_DIR = ROOT / "data" / "wechat_groups" / "processed"
ARCHIVE_DIR = ROOT / "data" / "wechat_groups" / "archives"
INDEX_JSON = PROCESSED_DIR / "index.json"
INDEX_MD = PROCESSED_DIR / "index.md"
SH = ZoneInfo("Asia/Shanghai")

KEYWORDS = [
    "AI", "算力", "存储", "DRAM", "HBM", "半导体", "光模块", "机器人", "新能源", "港股", "A股", "美股",
    "加仓", "减仓", "买入", "卖出", "调研", "订单", "业绩", "估值", "风险", "流动性",
]


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, text[end + 5 :].strip()


def _extract_keywords(text: str) -> list[str]:
    lowered = text.lower()
    return [kw for kw in KEYWORDS if kw.lower() in lowered]


def _extract_tickers(text: str) -> list[str]:
    return sorted(set(re.findall(r"(?<![A-Za-z])\$?[A-Z]{2,6}(?![A-Za-z])", text)))[:20]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _load_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(INBOX_DIR.glob("*/*.md")):
        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if not body:
            continue
        preview = re.sub(r"\s+", " ", body).strip()[:300]
        records.append(
            {
                "group": meta.get("group") or path.parent.name,
                "messageId": meta.get("messageId") or path.stem,
                "importedAt": meta.get("importedAt") or "",
                "path": path.as_posix(),
                "keywords": _extract_keywords(body),
                "tickers": _extract_tickers(body),
                "preview": preview,
                "body": body,
            }
        )
    return records


def _write_index(records: list[dict[str, Any]]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    public_records = [{k: v for k, v in item.items() if k != "body"} for item in records]
    INDEX_JSON.write_text(json.dumps(public_records, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 微信投资群消息索引", ""]
    for item in public_records:
        tags = ", ".join(_dedupe(item["keywords"] + item["tickers"]))
        lines.append(f"- {item['importedAt']}｜{item['group']}｜{tags}｜{item['preview']}")
    INDEX_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _record_date(item: dict[str, Any], now: dt.datetime) -> dt.date:
    imported_at = item.get("importedAt") or ""
    try:
        return dt.datetime.fromisoformat(imported_at).date()
    except ValueError:
        return now.date()


def _write_daily_archive(records: list[dict[str, Any]], now: dt.datetime) -> list[Path]:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    by_date: dict[dt.date, list[dict[str, Any]]] = {}
    for item in records:
        by_date.setdefault(_record_date(item, now), []).append(item)

    paths: list[Path] = []
    for day, items in sorted(by_date.items()):
        groups = _dedupe([item["group"] for item in items])
        keywords = _dedupe([kw for item in items for kw in item["keywords"]])
        tickers = _dedupe([ticker for item in items for ticker in item["tickers"]])
        path = ARCHIVE_DIR / f"{day.isoformat()}_微信群原文归档.md"
        lines = [
            "---",
            f"date: {day.isoformat()}",
            f"generated_at: {now.isoformat()}",
            'title: "微信群原文归档"',
            f"message_batches: {len(items)}",
            f"groups: \"{', '.join(groups)}\"",
            "---",
            "",
            "# 微信群原文归档",
            "",
            f"- 日期：{day.isoformat()}",
            f"- 群组：{', '.join(groups)}",
            f"- 消息批次：{len(items)}",
            f"- 关键词：{', '.join(keywords) or '无'}",
            f"- 股票/代码线索：{', '.join(tickers) or '无'}",
            "",
            "## 原文",
            "",
        ]
        for index, item in enumerate(items, start=1):
            lines += [
                f"### 消息批次 {index}",
                "",
                f"- 群组：{item['group']}",
                f"- 导入时间：{item['importedAt']}",
                f"- 关键词：{', '.join(_dedupe(item['keywords'] + item['tickers'])) or '无'}",
                "",
                item["body"].strip(),
                "",
            ]
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def main() -> int:
    now = dt.datetime.now(SH)
    records = _load_records()
    _write_index(records)
    archive_paths = _write_daily_archive(records, now)
    print(f"[OK] processed group messages: {len(records)}")
    for path in archive_paths:
        print(f"[OK] archive -> {path}")
    if not archive_paths:
        print("[OK] archive skipped: no inbox messages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
