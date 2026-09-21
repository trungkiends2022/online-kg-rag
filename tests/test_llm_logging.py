import json
import time

from src.llm import client


class FakeProvider:
    name = "fake"
    model = "fake-model"

    def complete(self, prompt, *, max_tokens):
        return f"reply:{prompt}"


def test_llm_call_writes_metadata_without_content(monkeypatch, tmp_path):
    log_path = tmp_path / "calls.jsonl"
    monkeypatch.setenv("LLM_LOG_ENABLED", "true")
    monkeypatch.setenv("LLM_LOG_PATH", str(log_path))
    monkeypatch.delenv("LLM_LOG_CONTENT", raising=False)
    monkeypatch.setattr(client, "_provider", FakeProvider())

    assert client.llm_call("secret", max_tokens=7) == "reply:secret"

    record = json.loads(log_path.read_text(encoding="utf-8"))
    assert record["provider"] == "fake"
    assert record["model"] == "fake-model"
    assert record["max_tokens"] == 7
    assert record["status"] == "ok"
    assert record["prompt_chars"] == 6
    assert record["response_chars"] == 12
    assert "prompt" not in record
    assert "response" not in record


def test_llm_call_forwards_explicit_temperature(monkeypatch):
    received = {}

    class TemperatureProvider:
        name = "fake"
        model = "fake-model"

        def complete(self, prompt, *, max_tokens, temperature=None):
            received.update(max_tokens=max_tokens, temperature=temperature)
            return "ok"

    monkeypatch.setattr(client, "_provider", TemperatureProvider())

    assert client.llm_call("prompt", max_tokens=11, temperature=0.0) == "ok"
    assert received == {"max_tokens": 11, "temperature": 0.0}


def test_capture_llm_metrics_collects_calls(monkeypatch):
    monkeypatch.setattr(client, "_provider", FakeProvider())

    with client.capture_llm_metrics() as metrics:
        client.llm_call("one", max_tokens=3)
        client.llm_call("two", max_tokens=3)

    assert metrics["llm_calls"] == 2
    assert metrics["llm_successful_calls"] == 2
    assert metrics["llm_failed_calls"] == 0
    assert metrics["llm_prompt_chars"] == 6
    assert metrics["llm_response_chars"] == len("reply:one") + len("reply:two")
    assert metrics["llm_latency_ms"] >= 0


def test_rate_limit_retry_counts_api_attempts(monkeypatch):
    class RateLimitError(Exception):
        pass

    class FlakyProvider:
        name = "fake"
        model = "fake-model"

        def __init__(self):
            self.calls = 0

        def complete(self, prompt, *, max_tokens):
            self.calls += 1
            if self.calls == 1:
                raise RateLimitError("Please try again in 0.01s")
            return "ok"

    provider = FlakyProvider()
    monkeypatch.setattr(client, "_provider", provider)
    monkeypatch.setattr(client.time, "sleep", lambda seconds: None)

    with client.capture_llm_metrics() as metrics:
        assert client.llm_call("prompt") == "ok"

    assert metrics["llm_calls"] == 1
    assert metrics["llm_api_attempts"] == 2
    assert metrics["llm_successful_calls"] == 1


def test_llm_call_many_runs_independent_prompts_concurrently(monkeypatch):
    class SlowProvider:
        name = "fake"
        model = "fake-model"

        def complete(self, prompt, *, max_tokens):
            time.sleep(0.04)
            return prompt.upper()

    monkeypatch.setattr(client, "_provider", SlowProvider())
    started = time.perf_counter()
    with client.capture_llm_metrics() as metrics:
        assert client.llm_call_many(["one", "two", "three"], max_workers=3) == ["ONE", "TWO", "THREE"]
    assert time.perf_counter() - started < 0.1
    assert metrics["llm_calls"] == 3
