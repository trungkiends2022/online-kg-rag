"""Provider for Groq's OpenAI-compatible API."""

from __future__ import annotations

import os

from src.llm.base import LLMProvider


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        from openai import OpenAI

        self.model = model or os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
        self._client = OpenAI(
            api_key=api_key or os.environ.get("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
        )

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
