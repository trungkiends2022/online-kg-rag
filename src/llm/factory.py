"""Factory: chọn LLM provider theo tên (config/env), lazy-import để không bắt cài
hết mọi SDK nếu chỉ dùng 1 provider."""

from __future__ import annotations

from src.llm.base import LLMProvider

_REGISTRY = {
    "anthropic": "src.llm.providers.anthropic_provider.AnthropicProvider",
    "openai": "src.llm.providers.openai_provider.OpenAIProvider",
    "gemini": "src.llm.providers.gemini_provider.GeminiProvider",
    "openai_compatible": "src.llm.providers.openai_compatible_provider.OpenAICompatibleProvider",
}


def create_provider(name: str, **kwargs) -> LLMProvider:
    if name not in _REGISTRY:
        raise ValueError(
            f"Unknown LLM provider '{name}'. Available: {list(_REGISTRY.keys())}"
        )
    module_path, class_name = _REGISTRY[name].rsplit(".", 1)
    import importlib

    module = importlib.import_module(module_path)
    provider_cls = getattr(module, class_name)
    return provider_cls(**kwargs)
