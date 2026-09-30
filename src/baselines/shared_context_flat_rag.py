"""Flat RAG baseline over the same two-stage evidence used by KG methods."""

from __future__ import annotations

import json
import time

from src.baselines.rag_variants import RAGConfig, _RAGBaseline
from src.datasets.schema import DatasetExample
from src.retrieval.coarse_retrieval import two_stage_retrieve


class SharedContextFlatRAGBaseline(_RAGBaseline):
    """Answer from KG-retrieved table rows and passages without a graph or paths."""

    method_name = "flat_rag_shared_context"

    @staticmethod
    def _row_blocks(table_groups: list[dict]) -> list[dict]:
        blocks: list[dict] = []
        for table_index, group in enumerate(table_groups):
            table_name = str(group.get("table_name", f"table_{table_index}"))
            rows = list(group.get("rows", []))
            row_indices = list(group.get("row_indices", range(len(rows))))
            links_by_row: dict[int, list[dict]] = {}
            for link in group.get("cell_links", []):
                if link.get("row_index") is not None:
                    links_by_row.setdefault(int(link["row_index"]), []).append(dict(link))
            for row, row_index in zip(rows, row_indices):
                blocks.append({
                    "table_name": table_name,
                    "row_index": int(row_index),
                    "row": row,
                    "cell_links": links_by_row.get(int(row_index), []),
                })
        return blocks

    def _bounded_table_context(self, table_groups: list[dict]) -> tuple[str, list[int], bool]:
        budget = max(1, self.config.max_context_chars // 2)
        selected: list[dict] = []
        all_blocks = self._row_blocks(table_groups)
        for block in all_blocks:
            candidate = [*selected, block]
            if len(json.dumps(candidate, ensure_ascii=False)) <= budget:
                selected.append(block)
        return (
            json.dumps(selected, ensure_ascii=False),
            [block["row_index"] for block in selected],
            len(selected) < len(all_blocks),
        )

    @staticmethod
    def _passage_block(passage: dict) -> str:
        context_before = str(passage.get("context_before", "")).strip()
        text = str(passage.get("text", "")).strip()
        contents = "\n".join(part for part in (context_before, text) if part)
        return f'[{passage["id"]}] {contents}'

    def run(self, example: DatasetExample) -> dict:
        started = time.perf_counter()
        retrieved = two_stage_retrieve(
            example.question,
            example.table_rows,
            example.text_passages,
            example.web_snippets,
            top_k=self.config.top_k,
            second_stage_k=self.config.second_stage_k,
            max_table_rows=self.config.max_table_rows_for_kg,
        )
        table_text, row_indices, table_truncated = self._bounded_table_context(
            retrieved["table_rows"]
        )
        remaining = max(self.config.max_context_chars - len(table_text), 0)
        passage_blocks: list[str] = []
        passage_ids: list[str] = []
        for passage in retrieved["text_passages"]:
            block = self._passage_block(passage)
            if len(block) <= remaining:
                passage_blocks.append(block)
                passage_ids.append(str(passage["id"]))
                remaining -= len(block)
        prompt = f"""Answer the question using only the retrieved evidence below.
The table rows and passages are flat evidence: do not infer facts absent from them.
Return exactly one non-empty answer span on one line, with no explanation or label.

Question: {example.question}

Retrieved table rows (JSON):
{table_text}

Retrieved passages:
{chr(10).join(passage_blocks)}

Answer:"""
        retrieval_trace = dict(retrieved.get("retrieval_trace", {}))
        retrieval_trace.update(
            selected_table_row_indices=row_indices,
            table_context_budget_chars=self.config.max_context_chars // 2,
            passage_context_budget_chars=self.config.max_context_chars - len(table_text),
        )
        return self._complete(
            prompt,
            llm_calls=1,
            started=started,
            metadata={
                "retrieved_passage_ids": passage_ids,
                "table_truncated": table_truncated,
                "retrieval_trace": retrieval_trace,
                "prompt_chars": len(prompt),
                "top_k": self.config.top_k,
                "second_stage_k": self.config.second_stage_k,
                "context_policy": "two_stage_retrieval_flattened_without_kg",
            },
        )
