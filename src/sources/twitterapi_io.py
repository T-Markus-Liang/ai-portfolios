"""twitterapi.io adapter that returns normalized tweets."""

from __future__ import annotations

from ..fetch_x_data import get_user_last_tweets


def _normalize(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    for t in items or []:
        if not isinstance(t, dict):
            continue
        out.append(
            {
                "id": str(t.get("id") or ""),
                "text": (t.get("text") or "").strip(),
                "url": t.get("url") or t.get("twitterUrl") or "",
                "createdAt": t.get("createdAt", ""),
                "createdAtTs": 0.0,  # twitterapi.io has its own date string; not needed for ordering
                "likeCount": int(t.get("likeCount") or 0),
                "retweetCount": int(t.get("retweetCount") or 0),
                "source": "twitterapi.io",
            }
        )
    return out


def fetch_user_tweets(handle: str, count: int = 40) -> list[dict]:
    return _normalize(get_user_last_tweets(handle, count=count))
