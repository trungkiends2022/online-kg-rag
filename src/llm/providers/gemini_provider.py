"""Provider cho Google Gemini."""

from __future__ import annotations

import os

from src.llm.base import LLMProvider
from src.llm.runtime_config import request_timeout_seconds, sdk_max_retries


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        from google import genai
        from google.genai import types

        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
        self._client = genai.Client(
            api_key=api_key or os.environ.get("GEMINI_API_KEY"),
            http_options=types.HttpOptions(
                timeout=int(request_timeout_seconds() * 1000),
                retry_options=types.HttpRetryOptions(
                    attempts=sdk_max_retries() + 1,
                    initial_delay=1.0,
                    max_delay=30.0,
                    exp_base=2.0,
                    jitter=0.2,
                ),
            ),
        )

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
