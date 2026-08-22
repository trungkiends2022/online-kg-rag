"""Provider cho OpenAI (GPT series)."""

from __future__ import annotations

import os

from src.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        from openai import OpenAI

        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
        self._client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            max_completion_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""
