"""LLM client wrapper. Đọc ANTHROPIC_API_KEY từ .env, gọi Claude, trả về text."""

from __future__ import annotations

import os
import json
import re

from dotenv import load_dotenv

load_dotenv()

_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


def llm_call(prompt: str, *, json_mode: bool = False, max_tokens: int = 1024) -> str:
    """
    Gọi LLM thật. Nếu json_mode=True, cố gắng strip markdown fence trước khi trả về
    (caller vẫn nên tự json.loads và validate).
    """
    client = _get_client()
    resp = client.messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")

    if json_mode:
        text = re.sub(r"^```json\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return text


def llm_call_json(prompt: str, *, max_tokens: int = 1024):
    """Tiện ích: gọi LLM và parse JSON luôn, raise rõ ràng nếu parse lỗi."""
    raw = llm_call(prompt, json_mode=True, max_tokens=max_tokens)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM không trả JSON hợp lệ:\n{raw}") from e
