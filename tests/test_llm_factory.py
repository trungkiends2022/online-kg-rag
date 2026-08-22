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


def test_switch_provider_via_env(monkeypatch):
    import src.llm.client as client_module

    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    provider = client_module.get_provider(force_reload=True)
    assert provider.name == "anthropic"
