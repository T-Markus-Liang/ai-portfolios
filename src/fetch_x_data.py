"""Read-only fetch helpers for twitterapi.io.

Free-tier limit is ~1 QPS (one request per 5 seconds). We enforce
a >5s gap between requests and retry once on HTTP 429.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests

BASE_URL = "https://api.twitterapi.io"
MIN_INTERVAL_S = 5.5  # free-tier safety margin


class TwitterAPIError(RuntimeError):
    pass


_LAST_CALL_TS: float = 0.0


def _key() -> str:
    key = os.environ.get("TWITTERAPI_IO_KEY", "").strip()
    if not key:
        raise TwitterAPIError("TWITTERAPI_IO_KEY is not set")
    return key


def _respect_qps() -> None:
    global _LAST_CALL_TS
    elapsed = time.time() - _LAST_CALL_TS
    if elapsed < MIN_INTERVAL_S:
        time.sleep(MIN_INTERVAL_S - elapsed)
    _LAST_CALL_TS = time.time()


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    _respect_qps()
    resp = requests.get(
        f"{BASE_URL}{path}",
        headers={"x-api-key": _key()},
        params=params,
        timeout=20,
    )
    if resp.status_code == 429:
        # back off and retry once
        time.sleep(MIN_INTERVAL_S)
        _respect_qps()
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
    return _get("/twitter/user/last_tweets", {"userName": username, "count": count})


def fetch_kol_recent(handles: list[str], count_per_user: int = 10) -> list[dict[str, Any]]:
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
    return items
