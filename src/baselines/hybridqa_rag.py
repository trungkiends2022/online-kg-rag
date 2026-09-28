"""Table-aware zero-shot RAG baseline for HybridQA."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from src.datasets.schema import DatasetExample
from src.llm.client import get_provider, llm_call
from src.retrieval.coarse_retrieval import two_stage_retrieve


_RAW_RESPONSE_LIMIT = 512


@dataclass(frozen=True)
class BaselineConfig:
    passage_top_k: int = 5
    second_stage_k: int = 3
    max_context_chars: int = 24_000
    max_output_tokens: int = 128
    temperature: float = 0.0
    table_context_fraction: float = 0.5


class HybridQARAGBaseline:
    """Answer from table rows plus row-conditioned, retrieved passages."""

    method_name = "oracle_table_row_bm25_rag"

    def __init__(self, config: BaselineConfig | None = None):
        self.config = config or BaselineConfig()
        if self.config.passage_top_k < 0 or self.config.second_stage_k < 0:
            raise ValueError("retrieval budgets must be non-negative")
        if self.config.max_context_chars <= 0 or self.config.max_output_tokens <= 0:
            raise ValueError("context and output limits must be positive")
        if not 0 < self.config.table_context_fraction < 1:
            raise ValueError("table_context_fraction must be between zero and one")

    @staticmethod
    def _bounded(value: str | None, limit: int = _RAW_RESPONSE_LIMIT) -> str:
        value = str(value or "").strip()
        return value if len(value) <= limit else value[: limit - 1] + "…"

    @staticmethod
    def _needs_retry(answer: str) -> bool:
        answer = str(answer or "").strip()
        placeholders = {"unknown", "n/a", "na", "null", "none", "insufficient information"}
        return (not answer or answer.casefold() in placeholders or len(answer) > 256
                or "\n" in answer or bool(re.match(r"^(?:answer|final answer)\s*:", answer, re.I)))

    @staticmethod
    def _row_blocks(table_groups: list[dict]) -> list[dict]:
        blocks: list[dict] = []
        for table_index, group in enumerate(table_groups):
            name = str(group.get("table_name", f"table_{table_index}"))
            indices = group.get("row_indices", range(len(group.get("rows", []))))
            links_by_row: dict[int, list[dict]] = {}
            for link in group.get("cell_links", []):
                if link.get("row_index") is not None:
                    links_by_row.setdefault(int(link["row_index"]), []).append(dict(link))
            for row, row_index in zip(group.get("rows", []), indices):
                blocks.append({"table_name": name, "row_index": row_index, "row": row,
                               "cell_links": links_by_row.get(int(row_index), [])})
        return blocks

    def _bounded_table_context(self, table_groups: list[dict]) -> tuple[str, list[int], bool]:
        """Emit selected whole rows, never a character-sliced JSON table."""
        budget = max(1, int(self.config.max_context_chars * self.config.table_context_fraction))
        all_blocks = self._row_blocks(table_groups)
        selected: list[dict] = []
        for block in all_blocks:
            if len(json.dumps([*selected, block], ensure_ascii=False)) <= budget:
                selected.append(block)
        return (json.dumps(selected, ensure_ascii=False),
                [int(block["row_index"]) for block in selected],
                len(selected) < len(all_blocks))

    @staticmethod
    def _request_token_limit(provider, configured: int) -> int:
        """GPT-OSS needs completion room for hidden reasoning before final text."""
        model = str(getattr(provider, "model", "")).casefold()
        return max(configured, 512) if "gpt-oss" in model else configured

    def build_prompt(self, example: DatasetExample) -> tuple[str, list[str], bool, dict]:
        retrieved = two_stage_retrieve(
            example.question, example.table_rows, example.text_passages,
            example.web_snippets, top_k=self.config.passage_top_k,
            second_stage_k=self.config.second_stage_k,
            # Direct LLM retains its existing bounded table-prompt behaviour;
            # the unlimited default is reserved for KG construction.
            max_table_rows=self.config.passage_top_k,
        )
        table_text, row_indices, table_truncated = self._bounded_table_context(retrieved["table_rows"])
        remaining = max(self.config.max_context_chars - len(table_text), 0)
        selected_passages, passage_blocks = [], []
        for passage in retrieved["text_passages"]:
            block = f'[{passage["id"]}] {passage["text"]}'
            if len(block) <= remaining:
                passage_blocks.append(block)
                selected_passages.append(str(passage["id"]))
                remaining -= len(block)
        prompt = f"""Answer the question using only the table rows and passages below.
Return exactly one non-empty, single-line answer span. Start immediately with the answer; do not explain, label, quote, or return `unknown`, `N/A`, or a blank value.

Question: {example.question}

Selected table rows (JSON):
{table_text}

Passages:
{chr(10).join(passage_blocks)}

Answer:"""
        trace = dict(retrieved.get("retrieval_trace", {}))
        trace.update(selected_table_row_indices=row_indices,
                     table_context_budget_chars=int(self.config.max_context_chars * self.config.table_context_fraction),
                     passage_context_budget_chars=self.config.max_context_chars - len(table_text))
        return prompt, selected_passages, table_truncated, trace

    @staticmethod
    def _retry_prompt(question: str, previous: str) -> str:
        return f"""Your prior response was invalid. Reply now with exactly one non-empty, single-line answer span.
Start immediately with the answer. Do not explain, label, quote, return `unknown`/`N/A`, or leave it blank.
Question: {question}
Previous invalid response: {previous}
Answer:"""

    def run(self, example: DatasetExample) -> dict:
        prompt, passage_ids, table_truncated, retrieval_trace = self.build_prompt(example)
        provider = get_provider()
        started = time.perf_counter()
        request_max_tokens = self._request_token_limit(provider, self.config.max_output_tokens)
        raw_answer = llm_call(prompt, max_tokens=request_max_tokens,
                              temperature=self.config.temperature)
        answer = str(raw_answer or "").strip()
        retry_attempted = self._needs_retry(answer)
        retry_raw_answer = None
        if retry_attempted:
            retry_raw_answer = llm_call(
                self._retry_prompt(example.question, self._bounded(answer, 128)),
                max_tokens=max(512, request_max_tokens), temperature=self.config.temperature,
            )
            retry_answer = str(retry_raw_answer or "").strip()
            if not self._needs_retry(retry_answer):
                answer = retry_answer
        return {
            "answer": answer, "method": self.method_name, "provider": provider.name,
            "model": getattr(provider, "model", None), "passage_top_k": self.config.passage_top_k,
            "retrieved_passage_ids": passage_ids, "table_truncated": table_truncated,
            "retrieval_trace": retrieval_trace, "prompt_chars": len(prompt),
            "max_context_chars": self.config.max_context_chars,
            "max_output_tokens": self.config.max_output_tokens,
            "request_max_output_tokens": request_max_tokens, "temperature": self.config.temperature,
            "answer_retry_attempted": retry_attempted,
            "answer_response_valid": not self._needs_retry(answer),
            "raw_answer": self._bounded(raw_answer),
            "retry_raw_answer": self._bounded(retry_raw_answer) if retry_attempted else None,
            "llm_calls": 2 if retry_attempted else 1,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
