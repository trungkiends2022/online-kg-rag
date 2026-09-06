"""
Provider cho bất kỳ endpoint nào tương thích OpenAI API (base_url tuỳ chỉnh):
Ollama, vLLM, LM Studio, DeepSeek, Qwen, OpenRouter, v.v.
"""

from __future__ import annotations

import os

from src.llm.base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compatible"

    def __init__(self, model: str | None = None, api_key: str | None = None, base_url: str | None = None):
        from openai import OpenAI

        self.model = model or os.environ.get("COMPAT_MODEL", "llama3.1")
        self._client = OpenAI(
            api_key=api_key or os.environ.get("COMPAT_API_KEY", "not-needed"),
            base_url=base_url or os.environ.get("COMPAT_BASE_URL", "http://localhost:11434/v1"),
        )

    def complete(self, prompt: str, *, max_tokens: int = 1024, temperature: float | None = None) -> str:
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if temperature is not None:
            kwargs["temperature"] = temperature
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
