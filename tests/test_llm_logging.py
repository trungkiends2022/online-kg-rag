import json

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
