import pytest

from src.llm.factory import create_provider
from src.llm.base import LLMProvider


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_provider("not_a_real_provider")


def test_anthropic_provider_instantiates(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
    provider = create_provider("anthropic")
    assert isinstance(provider, LLMProvider)
    assert provider.name == "anthropic"


def test_openai_provider_instantiates(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-for-test")
    provider = create_provider("openai")
    assert isinstance(provider, LLMProvider)
    assert provider.name == "openai"


def test_openai_compatible_provider_instantiates():
    provider = create_provider("openai_compatible", base_url="http://localhost:11434/v1")
    assert isinstance(provider, LLMProvider)
    assert provider.name == "openai_compatible"


def test_openrouter_provider_defaults_to_paid_deepseek_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    provider = create_provider("openrouter")
    assert isinstance(provider, LLMProvider)
    assert provider.name == "openrouter"
    assert provider.model == "deepseek/deepseek-v4-flash"
    assert str(provider._client.base_url) == "https://openrouter.ai/api/v1/"


def test_openrouter_reasoning_extension_is_opt_in(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")
    monkeypatch.setenv("OPENROUTER_REASONING_ENABLED", "true")
    provider = create_provider("openrouter")
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])

    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    assert provider.complete("hello", max_tokens=12) == "ok"
    assert captured["extra_body"] == {"reasoning": {"enabled": True}}


def test_openrouter_can_explicitly_disable_reasoning(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-test")
    monkeypatch.setenv("OPENROUTER_REASONING_ENABLED", "false")
    provider = create_provider("openrouter")
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])

    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    assert provider.complete("hello", max_tokens=12) == "ok"
    assert "extra_body" not in captured


def test_deepseek_provider_instantiates(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key-for-test")
    provider = create_provider("deepseek")
    assert isinstance(provider, LLMProvider)
    assert provider.name == "deepseek"
    assert provider.model == "deepseek-v4-flash"


def test_groq_provider_instantiates(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key-for-test")
    provider = create_provider("groq")
    assert isinstance(provider, LLMProvider)
    assert provider.name == "groq"
    assert provider.model == "openai/gpt-oss-20b"


def test_nvidia_nim_provider_instantiates(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-key-for-test")
    monkeypatch.setenv("NVIDIA_NIM_MODEL", "openai/gpt-oss-20b")
    provider = create_provider("nvidia_nim")
    assert isinstance(provider, LLMProvider)
    assert provider.name == "nvidia_nim"
    assert provider.model == "openai/gpt-oss-20b"


def test_switch_provider_via_env(monkeypatch):
    import src.llm.client as client_module

    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    provider = client_module.get_provider(force_reload=True)
    assert provider.name == "anthropic"
