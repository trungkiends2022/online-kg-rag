"""Provider cho OpenAI (GPT series)."""

from __future__ import annotations

import os

from src.llm.base import LLMProvider
from src.llm.runtime_config import request_timeout_seconds, sdk_max_retries


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        from openai import OpenAI

        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
        self._client = OpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            timeout=request_timeout_seconds(),
            max_retries=sdk_max_retries(),
        )

    def complete(self, prompt: str, *, max_tokens: int = 1024, temperature: float | None = None) -> str:
        kwargs = dict(
            model=self.model,
            max_completion_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if temperature is not None:
            kwargs["temperature"] = temperature
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
