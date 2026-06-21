"""Nitter RSS source.

We rotate through a list of Nitter instances and return the first one
that responds with a real RSS feed. Many public instances are now
gated by JS challenges (Anubis / Cloudflare); those are detected and
treated as failures so we move on to the next instance.
"""

from __future__ import annotations

import calendar
import email.utils as eut
import re
import time
from typing import Iterable
from xml.etree import ElementTree as ET

import requests

DEFAULT_INSTANCES: list[str] = [
    "https://nitter.net",
    # The rest are kept as best-effort fallbacks; most currently fail
    # due to anti-bot challenges, but the list is cheap to try.
    "https://nitter.poast.org",
    "https://nitter.privacyredirect.com",
    "https://nitter.tiekoetter.com",
    "https://nitter.space",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
}

ID_RE = re.compile(r"/status/(\d+)")
TIMEOUT_S = 12


class NitterError(RuntimeError):
    pass


def _looks_like_rss(text: str) -> bool:
    head = text[:400].lower()
    return ("<rss" in head) or ("<?xml" in head and "<rss" in text[:800].lower())


def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _parse_pubdate(s: str) -> tuple[str, float]:
    if not s:
        return "", 0.0
    try:
        tt = eut.parsedate_tz(s)
        if not tt:
            return s, 0.0
        ts = float(calendar.timegm(tt[:9])) - (tt[9] or 0)
        return s, ts
    except Exception:
        return s, 0.0


def _parse_feed(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []
    out: list[dict] = []
    for it in channel.findall("item"):
        link = (it.findtext("link") or "").strip()
        title = _strip_html(it.findtext("title") or "")
        desc = _strip_html(it.findtext("description") or "")
        pub = (it.findtext("pubDate") or "").strip()
        guid = (it.findtext("guid") or "").strip()

        m = ID_RE.search(link) or ID_RE.search(guid)
        tid = m.group(1) if m else ""
        # Use description if richer than title (RSS often has both)
        text = desc if len(desc) >= len(title) else title
        created_str, created_ts = _parse_pubdate(pub)
        # Normalize URL to canonical x.com
        url = link
        if "/status/" in url and "x.com" not in url and "twitter.com" not in url:
            # nitter links look like https://nitter.net/<u>/status/<id>#m
            try:
                idx = url.index("/status/")
                user = url[: idx].rsplit("/", 1)[-1]
                tid2 = ID_RE.search(url).group(1)  # type: ignore[union-attr]
                url = f"https://x.com/{user}/status/{tid2}"
            except Exception:
                pass
        out.append(
            {
                "id": tid,
                "text": text,
                "url": url,
                "createdAt": created_str,
                "createdAtTs": created_ts,
                "likeCount": 0,
                "retweetCount": 0,
                "source": "nitter",
            }
        )
    return out


def fetch_user_rss(
    handle: str,
    instances: Iterable[str] | None = None,
    timeout: float = TIMEOUT_S,
) -> list[dict]:
    """Try each Nitter instance until one returns parseable RSS."""
    handle = handle.lstrip("@").strip()
    last_err: str = ""
    for base in instances or DEFAULT_INSTANCES:
        url = f"{base.rstrip('/')}/{handle}/rss"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
        except requests.RequestException as exc:
            last_err = f"{base}: {exc.__class__.__name__}"
            continue
        if not resp.ok:
            last_err = f"{base}: HTTP {resp.status_code}"
            continue
        text = resp.text
        if not _looks_like_rss(text):
            last_err = f"{base}: anti-bot or empty feed"
            continue
        try:
            items = _parse_feed(text)
        except ET.ParseError as exc:
            last_err = f"{base}: parse error {exc}"
            continue
        if items:
            return items
        last_err = f"{base}: empty items"
    raise NitterError(last_err or "all nitter instances failed")
