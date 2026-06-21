"""Common normalized tweet shape shared by all sources."""

from __future__ import annotations

from typing import Any, TypedDict


class Tweet(TypedDict, total=False):
    id: str
    text: str
    url: str
    createdAt: str
    createdAtTs: float
    likeCount: int
    retweetCount: int
    source: str


def normalize_tweets(items: list[dict[str, Any]]) -> list[Tweet]:
    out: list[Tweet] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if not it.get("id") and not it.get("url"):
            continue
        out.append(it)
    return out
