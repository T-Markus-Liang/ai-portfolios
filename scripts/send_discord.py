"""Send a markdown report to a Discord channel via webhook.

Usage:
    python scripts/send_discord.py <path-to-markdown-file> [--title "..."]

If the content exceeds Discord's 2000-char limit, the file is uploaded
as an attachment instead.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DISCORD_CONTENT_LIMIT = 1900  # leave headroom for code fences


def send(webhook: str, file_path: Path, title: str | None) -> int:
    text = file_path.read_text(encoding="utf-8")
    header = f"**{title}**\n" if title else ""

    if len(text) + len(header) <= DISCORD_CONTENT_LIMIT:
        resp = requests.post(
            webhook,
            json={"content": header + text},
            timeout=30,
        )
    else:
        resp = requests.post(
            webhook,
            data={"content": header + f"(report attached, {len(text)} chars)"},
            files={"file": (file_path.name, text.encode("utf-8"), "text/markdown")},
            timeout=60,
        )

    print(f"HTTP {resp.status_code}")
    if not resp.ok:
        print(resp.text, file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="markdown file to send")
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        print("ERROR: DISCORD_WEBHOOK_URL is not set.", file=sys.stderr)
        return 2

    file_path = Path(args.path)
    if not file_path.exists():
        print(f"ERROR: file not found: {file_path}", file=sys.stderr)
        return 2

    return send(webhook, file_path, args.title)


if __name__ == "__main__":
    raise SystemExit(main())
