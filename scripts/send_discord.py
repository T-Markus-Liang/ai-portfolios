"""Send a report file to a Discord channel via webhook.

Usage:
    python scripts/send_discord.py <path-to-report-file> [--title "..."]

Markdown files under the content limit are sent inline. Longer markdown,
PDFs, and other files are uploaded as attachments.
"""

from __future__ import annotations

import argparse
import mimetypes
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
    header = f"**{title}**\n" if title else ""
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"

    if file_path.suffix.lower() in {".md", ".txt"}:
        text = file_path.read_text(encoding="utf-8")
    else:
        text = ""

    if text and len(text) + len(header) <= DISCORD_CONTENT_LIMIT:
        resp = requests.post(
            webhook,
            json={"content": header + text},
            timeout=30,
        )
    else:
        size = file_path.stat().st_size
        content = header + f"(report attached, {file_path.name}, {size} bytes)"
        resp = requests.post(
            webhook,
            data={"content": content},
            files={"file": (file_path.name, file_path.read_bytes(), mime)},
            timeout=60,
        )

    print(f"HTTP {resp.status_code}")
    if not resp.ok:
        print(resp.text, file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="report file to send")
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
