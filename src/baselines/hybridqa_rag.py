"""Zero-shot oracle-context vanilla RAG baseline for HybridQA."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

from src.datasets.schema import DatasetExample
from src.llm.client import get_provider, llm_call
from src.retrieval.coarse_retrieval import coarse_retrieve


@dataclass(frozen=True)
class BaselineConfig:
    passage_top_k: int = 5
    max_context_chars: int = 24_000
    max_output_tokens: int = 1024
    temperature: float = 0.0


class HybridQARAGBaseline:
    """Answer directly from serialized table + BM25 passages, without a KG."""

    method_name = "oracle_context_bm25_vanilla_rag"

    def __init__(self, config: BaselineConfig | None = None):
        self.config = config or BaselineConfig()
        if self.config.passage_top_k < 0:
            raise ValueError("passage_top_k must be non-negative")
        if self.config.max_context_chars <= 0:
            raise ValueError("max_context_chars must be positive")
        if self.config.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")

    def build_prompt(self, example: DatasetExample) -> tuple[str, list[str], bool]:
        retrieved = coarse_retrieve(
            example.question,
            example.table_rows,
            example.text_passages,
            example.web_snippets,
            top_k=self.config.passage_top_k,
        )
        # HybridQA supplies one oracle table per question. Keep it intact; top-k
        # applies only to linked passages and must not silently drop table rows.
        table_text = json.dumps(example.table_rows, ensure_ascii=False)
        table_truncated = len(table_text) > self.config.max_context_chars
        table_text = table_text[: self.config.max_context_chars]
        remaining = max(self.config.max_context_chars - len(table_text), 0)
        selected_passages = []
        passage_blocks = []
        for passage in retrieved["text_passages"]:
            block = f'[{passage["id"]}] {passage["text"]}'
            if len(block) > remaining:
                break
            passage_blocks.append(block)
            selected_passages.append(passage["id"])
            remaining -= len(block)

        prompt = f"""Answer the question using only the table and passages below.
Return only the shortest answer span. Do not explain your reasoning.

Question: {example.question}

Table (JSON):
{table_text}

Passages:
{chr(10).join(passage_blocks)}

Answer:"""
        return prompt, selected_passages, table_truncated

    def run(self, example: DatasetExample) -> dict:
        prompt, passage_ids, table_truncated = self.build_prompt(example)
        provider = get_provider()
        started = time.perf_counter()
        answer = llm_call(
            prompt,
            max_tokens=self.config.max_output_tokens,
            temperature=self.config.temperature,
        ).strip()
        return {
            "answer": answer,
            "method": self.method_name,
            "provider": provider.name,
            "model": getattr(provider, "model", None),
            "passage_top_k": self.config.passage_top_k,
            "retrieved_passage_ids": passage_ids,
            "table_truncated": table_truncated,
            "prompt_chars": len(prompt),
            "max_context_chars": self.config.max_context_chars,
            "max_output_tokens": self.config.max_output_tokens,
            "temperature": self.config.temperature,
            "llm_calls": 1,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
