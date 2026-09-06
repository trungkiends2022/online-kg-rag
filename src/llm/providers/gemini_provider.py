"""Provider cho Google Gemini."""

from __future__ import annotations

import os

from src.llm.base import LLMProvider


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        from google import genai

        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-pro")
        self._client = genai.Client(api_key=api_key or os.environ.get("GEMINI_API_KEY"))

    def complete(self, prompt: str, *, max_tokens: int = 1024, temperature: float | None = None) -> str:
        config = {"max_output_tokens": max_tokens}
        if temperature is not None:
            config["temperature"] = temperature
        resp = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )
        return resp.text or ""
