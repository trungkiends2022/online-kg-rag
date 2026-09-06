"""Provider for NVIDIA's hosted NIM OpenAI-compatible API."""

from __future__ import annotations

import os

from src.llm.base import LLMProvider


class NvidiaNIMProvider(LLMProvider):
    name = "nvidia_nim"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        from openai import OpenAI

        self.model = model or os.environ.get("NVIDIA_NIM_MODEL", "openai/gpt-oss-20b")
        self._client = OpenAI(
            api_key=api_key or os.environ.get("NVIDIA_API_KEY"),
            base_url="https://integrate.api.nvidia.com/v1",
        )

    def complete(self, prompt: str, *, max_tokens: int = 1024, temperature: float | None = None) -> str:
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if temperature is not None:
            kwargs["temperature"] = temperature
        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""
