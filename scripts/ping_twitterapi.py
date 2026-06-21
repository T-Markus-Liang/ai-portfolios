"""Ping twitterapi.io to verify the API key works.

Usage:
    python scripts/ping_twitterapi.py [username]

Reads TWITTERAPI_IO_KEY from environment or .env file.
"""

from __future__ import annotations

import json
import os
import sys

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def main() -> int:
    api_key = os.environ.get("TWITTERAPI_IO_KEY", "").strip()
    if not api_key:
        print("ERROR: TWITTERAPI_IO_KEY is not set. Put it in .env or export it.", file=sys.stderr)
        return 2

    username = sys.argv[1] if len(sys.argv) > 1 else "elonmusk"
    url = "https://api.twitterapi.io/twitter/user/info"
    try:
        resp = requests.get(
            url,
            headers={"x-api-key": api_key},
            params={"userName": username},
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"ERROR: request failed: {exc}", file=sys.stderr)
        return 1

    print(f"HTTP {resp.status_code}")
    try:
        print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
    except ValueError:
        print(resp.text)
    return 0 if resp.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
