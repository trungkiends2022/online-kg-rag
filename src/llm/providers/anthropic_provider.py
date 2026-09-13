"""Provider cho Claude (Anthropic API)."""

from __future__ import annotations

import os

from src.llm.base import LLMProvider
from src.llm.runtime_config import request_timeout_seconds, sdk_max_retries


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        import anthropic

        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            timeout=request_timeout_seconds(),
            max_retries=sdk_max_retries(),
        )

    def complete(self, prompt: str, *, max_tokens: int = 1024, temperature: float | None = None) -> str:
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if temperature is not None:
            kwargs["temperature"] = temperature
        resp = self._client.messages.create(**kwargs)
        return "".join(block.text for block in resp.content if block.type == "text")
