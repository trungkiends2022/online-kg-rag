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
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from src.llm.factory import create_provider
from src.llm.base import LLMProvider

load_dotenv()

_provider: LLMProvider | None = None
_provider_lock = threading.Lock()
_log_lock = threading.Lock()
_metrics_lock = threading.Lock()
_metrics_context: ContextVar[dict | None] = ContextVar("llm_metrics", default=None)
_rate_lock = threading.Lock()
_last_request_at: dict[str, float] = {}


def _pace_provider(provider_name: str) -> None:
    specific = f"{provider_name.upper()}_MIN_REQUEST_INTERVAL_SECONDS"
    interval = float(
        os.environ.get(specific, os.environ.get("LLM_MIN_REQUEST_INTERVAL_SECONDS", "0"))
    )
    if interval <= 0:
        return
    with _rate_lock:
        now = time.monotonic()
        wait_for = interval - (now - _last_request_at.get(provider_name, 0.0))
        if wait_for > 0:
            time.sleep(wait_for)
        _last_request_at[provider_name] = time.monotonic()


@contextmanager
def capture_llm_metrics():
    """Collect per-run LLM performance counters without changing provider APIs."""
    metrics = {
        "llm_calls": 0,
        "llm_api_attempts": 0,
        "llm_successful_calls": 0,
        "llm_failed_calls": 0,
        "llm_prompt_chars": 0,
        "llm_response_chars": 0,
        "llm_latency_ms": 0.0,
    }
    token = _metrics_context.set(metrics)
    try:
        yield metrics
    finally:
        _metrics_context.reset(token)


def _capture_call(record: dict) -> None:
    metrics = _metrics_context.get()
    if metrics is None:
        return
    with _metrics_lock:
        metrics["llm_calls"] += 1
        metrics["llm_api_attempts"] += int(record.get("api_attempts", 1))
        metrics["llm_prompt_chars"] += int(record.get("prompt_chars", 0))
        metrics["llm_response_chars"] += int(record.get("response_chars", 0))
        metrics["llm_latency_ms"] += float(record.get("duration_ms", 0.0))
        if record.get("status") == "ok":
            metrics["llm_successful_calls"] += 1
        else:
            metrics["llm_failed_calls"] += 1


def _env_enabled(name: str) -> bool:
    return os.environ.get(name, "").lower() in {"1", "true", "yes", "on"}


def _write_call_log(record: dict) -> None:
    """Append one JSON object per LLM call. API keys are never included."""
    if not _env_enabled("LLM_LOG_ENABLED"):
        return
    path = Path(os.environ.get("LLM_LOG_PATH", "logs/llm_calls.jsonl"))
    path.parent.mkdir(parents=True, exist_ok=True)
    # Multiple benchmark workers can finish at the same time.  One locked write
    # keeps JSONL records intact without serializing the provider requests.
    with _log_lock:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_provider(force_reload: bool = False) -> LLMProvider:
    """Trả về provider hiện hành (lazy singleton). force_reload=True để đổi provider
    giữa chừng (VD trong test, hoặc khi muốn so sánh nhiều model cho cùng 1 câu hỏi)."""
    global _provider
    if _provider is None or force_reload:
        with _provider_lock:
            if _provider is None or force_reload:
                name = os.environ.get("LLM_PROVIDER", "anthropic")
                _provider = create_provider(name)
    return _provider


def set_provider(name: str, **kwargs) -> None:
    """Đổi provider chủ động trong code, không qua env — hữu ích khi muốn chạy
    multi-model ensemble (VD self-consistency dùng 2 model khác nhau cho path khác nhau)."""
    global _provider
    _provider = create_provider(name, **kwargs)


def llm_call(
    prompt: str,
    *,
    json_mode: bool = False,
    max_tokens: int = 1024,
    temperature: float | None = None,
) -> str:
    provider = get_provider()
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    record = {
        "timestamp": started_at,
        "provider": provider.name,
        "model": getattr(provider, "model", None),
        "max_tokens": max_tokens,
        "temperature": temperature,
        "prompt_chars": len(prompt),
    }
    if _env_enabled("LLM_LOG_CONTENT"):
        record["prompt"] = prompt
    kwargs = {"max_tokens": max_tokens}
    if temperature is not None:
        kwargs["temperature"] = temperature
    api_attempts = 0
    max_rate_retries = int(os.environ.get("LLM_RATE_LIMIT_RETRIES", "3"))
    succeeded = False
    last_error: Exception | None = None
    while True:
        api_attempts += 1
        try:
            _pace_provider(provider.name)
            text = provider.complete(prompt, **kwargs)
            succeeded = True
            break
        except Exception as error:
            last_error = error
            status_code = getattr(error, "status_code", None)
            error_text = str(error)
            is_rate_limit = (
                type(error).__name__ == "RateLimitError"
                or status_code == 429
                or "RESOURCE_EXHAUSTED" in error_text
            )
            if not is_rate_limit or api_attempts > max_rate_retries:
                break
            match = re.search(r"(?:try again|retry) in\s+([\d.]+)s", error_text, re.IGNORECASE)
            delay = min(float(match.group(1)) + 0.25, 59.0) if match else min(2 ** api_attempts, 30.0)
            time.sleep(delay)
    if not succeeded:
        assert last_error is not None
        record.update(
            status="error",
            error_type=type(last_error).__name__,
            api_attempts=api_attempts,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        _capture_call(record)
        _write_call_log(record)
        raise last_error
    record.update(
        status="ok",
        api_attempts=api_attempts,
        response_chars=len(text),
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    if _env_enabled("LLM_LOG_CONTENT"):
        record["response"] = text
    _capture_call(record)
    _write_call_log(record)
    if json_mode:
        text = re.sub(r"^```json\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return text


def llm_call_json(
    prompt: str,
    *,
    max_tokens: int = 1024,
    retries: int = 1,
    temperature: float | None = None,
):
    """Call an LLM for JSON, retrying empty, malformed, or non-list output."""
    last_raw = ""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        retry_note = ""
        if attempt:
            retry_note = (
                "\nLần trả lời trước rỗng hoặc không phải JSON list hợp lệ. "
                "Hãy trả lại đầy đủ JSON list, không markdown và không giải thích."
            )
        last_raw = llm_call(
            prompt + retry_note,
            json_mode=True,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        try:
            parsed = _parse_json_list(last_raw)
            if not isinstance(parsed, list):
                raise TypeError("expected a JSON list")
            return parsed
        except (json.JSONDecodeError, TypeError) as exc:
            last_error = exc
    raise ValueError(
        f"LLM ({get_provider().name}) không trả JSON list hợp lệ sau "
        f"{retries + 1} lần:\n{last_raw}"
    ) from last_error


def llm_call_many(
    prompts: list[str],
    *,
    max_workers: int = 1,
    json_mode: bool = False,
    max_tokens: int = 1024,
    temperature: float | None = None,
) -> list[str]:
    """Complete several independent prompts concurrently, preserving order.

    Providers in this project expose blocking HTTP calls.  Threads overlap that
    network wait efficiently; this is intentionally not a CPU parallelism API.
    Rate pacing and retries remain enforced by :func:`llm_call`.
    """
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    if not prompts:
        return []

    def call(prompt: str) -> str:
        return llm_call(
            prompt,
            json_mode=json_mode,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    # ContextVars do not cross threads automatically.  Copy the caller's
    # metrics context so capture_llm_metrics() also works for batched calls.
    contexts = [copy_context() for _ in prompts]

    def call_in_context(index: int) -> str:
        return contexts[index].run(call, prompts[index])

    with ThreadPoolExecutor(max_workers=min(max_workers, len(prompts))) as executor:
        return list(executor.map(call_in_context, range(len(prompts))))


def _parse_json_list(raw: str) -> list:
    """Parse a list even when a provider adds a short prose prefix or fence.

    We deliberately do not try to repair incomplete JSON: accepting a truncated
    program is worse than retrying it.  ``raw_decode`` only relaxes harmless
    wrapping text produced by some OpenRouter models.
    """
    text = raw.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as original_error:
        start = text.find("[")
        if start < 0:
            raise original_error
        parsed, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(parsed, list):
        raise TypeError("expected a JSON list")
    return parsed
