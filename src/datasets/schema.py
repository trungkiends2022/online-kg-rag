"""A small, benchmark-independent input contract for :mod:`src.pipeline`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DatasetExample:
    example_id: str
    question: str
    table_rows: list[dict]
    text_passages: list[dict]
    web_snippets: list[dict] = field(default_factory=list)
    answer: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def pipeline_inputs(self) -> dict:
        """Return only the arguments accepted by ``OnlineKGPipeline.run``."""
        return {
            "question": self.question,
            "table_rows": self.table_rows,
            "text_passages": self.text_passages,
            "web_snippets": self.web_snippets,
        }
