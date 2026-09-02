"""
LLM client — provider-agnostic. Đọc LLM_PROVIDER từ .env để chọn Anthropic/OpenAI/
Gemini/OpenAI-compatible (Ollama, vLLM...), không cần đổi code ở các module khác
(extraction, planning, execution...) vì tất cả chỉ gọi llm_call()/llm_call_json().

Đổi provider chỉ cần đổi biến môi trường LLM_PROVIDER trong .env, ví dụ:
    LLM_PROVIDER=anthropic   ANTHROPIC_API_KEY=...  ANTHROPIC_MODEL=claude-sonnet-4-6
    LLM_PROVIDER=openai      OPENAI_API_KEY=...     OPENAI_MODEL=gpt-4o
    LLM_PROVIDER=gemini      GEMINI_API_KEY=...     GEMINI_MODEL=gemini-2.5-pro
    LLM_PROVIDER=openai_compatible  COMPAT_BASE_URL=http://localhost:11434/v1  COMPAT_MODEL=llama3.1
"""

from __future__ import annotations

import os
import re
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from src.llm.factory import create_provider
from src.llm.base import LLMProvider

load_dotenv()

_provider: LLMProvider | None = None


def _env_enabled(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}


def _write_call_log(record: dict) -> None:
    """Append one JSON object per LLM call. API keys are never included."""
    if not _env_enabled("LLM_LOG_ENABLED"):
        return
    path = Path(os.environ.get("LLM_LOG_PATH", "logs/llm_calls.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_provider(force_reload: bool = False) -> LLMProvider:
    """Trả về provider hiện hành (lazy singleton). force_reload=True để đổi provider
    giữa chừng (VD trong test, hoặc khi muốn so sánh nhiều model cho cùng 1 câu hỏi)."""
    global _provider
    if _provider is None or force_reload:
        name = os.environ.get("LLM_PROVIDER", "anthropic")
        _provider = create_provider(name)
    return _provider


def set_provider(name: str, **kwargs) -> None:
    """Đổi provider chủ động trong code, không qua env — hữu ích khi muốn chạy
    multi-model ensemble (VD self-consistency dùng 2 model khác nhau cho path khác nhau)."""
    global _provider
    _provider = create_provider(name, **kwargs)


def llm_call(prompt: str, *, json_mode: bool = False, max_tokens: int = 1024) -> str:
    provider = get_provider()
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    record = {
        "timestamp": started_at,
        "provider": provider.name,
        "model": getattr(provider, "model", None),
        "max_tokens": max_tokens,
        "prompt_chars": len(prompt),
    }
    if _env_enabled("LLM_LOG_CONTENT"):
        record["prompt"] = prompt
    try:
        text = provider.complete(prompt, max_tokens=max_tokens)
    except Exception as exc:
        record.update(
            status="error",
            error_type=type(exc).__name__,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        _write_call_log(record)
        raise
    record.update(
        status="ok",
        response_chars=len(text),
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    if _env_enabled("LLM_LOG_CONTENT"):
        record["response"] = text
    _write_call_log(record)
    if json_mode:
        text = re.sub(r"^```json\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return text


def llm_call_json(prompt: str, *, max_tokens: int = 1024):
    raw = llm_call(prompt, json_mode=True, max_tokens=max_tokens)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM ({get_provider().name}) không trả JSON hợp lệ:\n{raw}") from e
