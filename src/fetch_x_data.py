"""Read-only fetch helpers for twitterapi.io.

Only the endpoints needed for the MVP are wrapped here.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests

BASE_URL = "https://api.twitterapi.io"


class TwitterAPIError(RuntimeError):
    pass


def _key() -> str:
    key = os.environ.get("TWITTERAPI_IO_KEY", "").strip()
    if not key:
        raise TwitterAPIError("TWITTERAPI_IO_KEY is not set")
    return key


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    resp = requests.get(
        f"{BASE_URL}{path}",
        headers={"x-api-key": _key()},
        params=params,
        timeout=20,
    )
    if not resp.ok:
        raise TwitterAPIError(f"GET {path} -> {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def get_user_info(username: str) -> dict[str, Any]:
    return _get("/twitter/user/info", {"userName": username})


def get_user_last_tweets(username: str, count: int = 20) -> dict[str, Any]:
    # twitterapi.io exposes user last tweets via /twitter/user/last_tweets
    return _get("/twitter/user/last_tweets", {"userName": username, "count": count})


def fetch_kol_recent(handles: list[str], count_per_user: int = 10, sleep_s: float = 0.4) -> list[dict[str, Any]]:
    """Best-effort recent tweets per handle. Errors per user do not abort the run."""
    items: list[dict[str, Any]] = []
    for handle in handles:
        if not handle:
            continue
        try:
            data = get_user_last_tweets(handle, count=count_per_user)
        except TwitterAPIError as exc:
            items.append({"handle": handle, "error": str(exc)})
            continue
        items.append({"handle": handle, "data": data})
        time.sleep(sleep_s)
    return items
