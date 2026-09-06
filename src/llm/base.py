"""Interface chung cho mọi LLM provider. Mỗi provider chỉ cần implement complete()."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(
        self, prompt: str, *, max_tokens: int = 1024, temperature: float | None = None
    ) -> str:
        """Gửi prompt, trả về text thuần (chưa xử lý markdown fence/JSON)."""
        raise NotImplementedError
