"""LLM summarizer.

Uses an OpenAI-compatible client (default: Volcengine Ark coding endpoint)
to turn a list of normalized tweets into a Chinese investment-research brief.

Env vars:
  ARK_API_KEY     required
  ARK_BASE_URL    default https://ark.cn-beijing.volces.com/api/coding/v3
  ARK_MODEL       default kimi-k2.6
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/coding/v3"
DEFAULT_MODEL = "kimi-k2.6"

MAX_TWEETS = 200          # cap items fed into the model
MAX_TEXT_LEN = 600        # cap each tweet text length
MAX_OUTPUT_TOKENS = 1800  # ~6KB markdown, fits Discord with attachment fallback


class LLMError(RuntimeError):
    pass


def _pack(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packed: list[dict[str, Any]] = []
    for it in items[:MAX_TWEETS]:
        text = (it.get("text") or "").strip()
        if len(text) > MAX_TEXT_LEN:
            text = text[:MAX_TEXT_LEN] + "…"
        packed.append(
            {
                "kol": it.get("kol") or it.get("handle") or "",
                "text": text,
                "url": it.get("url") or "",
                "createdAt": it.get("createdAt") or "",
                "likes": it.get("likeCount") or 0,
                "retweets": it.get("retweetCount") or 0,
                "source": it.get("source") or "",
            }
        )
    return packed


def summarize(items: list[dict[str, Any]]) -> str:
    if OpenAI is None:
        raise LLMError("openai package not installed")
    api_key = os.environ.get("ARK_API_KEY", "").strip()
    if not api_key:
        raise LLMError("ARK_API_KEY is not set")

    base_url = (os.environ.get("ARK_BASE_URL") or DEFAULT_BASE_URL).strip()
    model = (os.environ.get("ARK_MODEL") or DEFAULT_MODEL).strip()

    system_prompt = (PROMPTS_DIR / "system.md").read_text(encoding="utf-8")
    user_template = (PROMPTS_DIR / "daily_brief.md").read_text(encoding="utf-8")
    payload = json.dumps(_pack(items), ensure_ascii=False)
    user_prompt = user_template.replace("{{items}}", payload)

    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=MAX_OUTPUT_TOKENS,
            temperature=0.3,
        )
    except Exception as exc:  # network / auth / model errors
        raise LLMError(f"{type(exc).__name__}: {exc}") from exc

    content = (resp.choices[0].message.content or "").strip()
    if not content:
        raise LLMError("empty response from model")
    return content
