"""Direct LLM baseline using compact prompt serialization (without graph topology).

This baseline isolates the contribution of compact prompt serialization
from the query-time evidence graph (multigraph schema, star centroids,
multi-hop paths, and two-tier adaptive reasoning).
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from src.datasets.schema import DatasetExample
from src.baselines.context_policy import all_instance_evidence_retrieval_args
from src.baselines.grounded_response import parse_response, response_contract
from src.baselines.hybridqa_rag import BaselineConfig
from src.llm.client import get_provider, llm_call
from src.retrieval.coarse_retrieval import two_stage_retrieve


_RAW_RESPONSE_LIMIT = 512


class DirectLLMCompactBaseline:
    """Answer from table rows and passages serialized in compact lossless format."""

    method_name = "direct_llm_compact"

    def __init__(self, config: BaselineConfig | None = None):
        self.config = config or BaselineConfig()
        if self.config.passage_top_k < 0 or self.config.second_stage_k < 0:
            raise ValueError("retrieval budgets must be non-negative")
        if self.config.max_context_chars <= 0 or self.config.max_output_tokens <= 0:
            raise ValueError("context and output limits must be positive")

    @staticmethod
    def _bounded(value: str | None, limit: int = _RAW_RESPONSE_LIMIT) -> str:
        value = str(value or "").strip()
        return value if len(value) <= limit else value[: limit - 1] + "…"

    @staticmethod
    def _request_token_limit(provider, configured: int) -> int:
        model = str(getattr(provider, "model", "")).casefold()
        return max(configured, 512) if "gpt-oss" in model else configured

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
                blocks.append({
                    "table_name": name,
                    "row_index": int(row_index),
                    "row": row,
                    "cell_links": links_by_row.get(int(row_index), []),
                })
        return blocks

    def build_prompt(self, example: DatasetExample) -> tuple[str, list[str], list[str], bool, dict, dict]:
        """Build compact prompt payload without any graph structure or paths."""
        retrieved = two_stage_retrieve(
            example.question, example.table_rows, example.text_passages,
            example.web_snippets, **all_instance_evidence_retrieval_args(example),
        )
        all_blocks = self._row_blocks(retrieved["table_rows"])
        
        # Build table alias legend
        tables: dict[str, str] = {}
        for block in all_blocks:
            tname = block["table_name"]
            if tname not in tables:
                tables[tname] = f"t{len(tables)}"
        table_legend = {short: full for full, short in tables.items()}

        # Build passage alias legend
        passages: dict[str, str] = {}
        for p in retrieved["text_passages"]:
            pid = str(p["id"])
            if pid not in passages:
                passages[pid] = f"p{len(passages)}"
        passage_legend = {short: full for full, short in passages.items()}

        # Context budget allocation: table rows and passages
        budget = self.config.max_context_chars
        table_fraction = getattr(self.config, "table_context_fraction", 0.5)
        table_budget = max(1, int(budget * table_fraction))

        # Build compact row records
        selected_blocks: list[dict] = []
        compact_rows: list[dict] = []
        for block in all_blocks:
            tshort = tables[block["table_name"]]
            r_idx = block["row_index"]
            row_dict = block["row"]
            # Extract linked passage aliases
            linked_passages = []
            for link in block.get("cell_links", []):
                lid = str(link.get("link") or link.get("passage_id") or "")
                if lid in passages:
                    linked_passages.append(passages[lid])
            row_entry = {
                "t": tshort,
                "r": f"r{r_idx}",
                "vals": dict(row_dict),
            }
            if linked_passages:
                row_entry["psg"] = sorted(set(linked_passages))
            test_rows = [*compact_rows, row_entry]
            if len(json.dumps(test_rows, ensure_ascii=False, separators=(",", ":"))) <= table_budget:
                compact_rows.append(row_entry)
                selected_blocks.append(block)
            else:
                break

        table_truncated = len(selected_blocks) < len(all_blocks)
        selected_row_ids = [
            f"{b['table_name']}:{b['row_index']}" for b in selected_blocks
        ]
        selected_row_aliases = [
            f"{tables[b['table_name']]}:r{b['row_index']}" for b in selected_blocks
        ]

        # Allocate remaining budget to compact contexts
        current_table_len = len(json.dumps(compact_rows, ensure_ascii=False, separators=(",", ":")))
        remaining_budget = max(0, budget - current_table_len)

        selected_passages: list[str] = []
        selected_passage_aliases: list[str] = []
        compact_contexts: list[dict] = []
        for p in retrieved["text_passages"]:
            pid = str(p["id"])
            p_alias = passages[pid]
            p_text = str(p.get("text", "")).strip()
            ctx_entry = {"id": p_alias, "text": p_text}
            test_contexts = [*compact_contexts, ctx_entry]
            if len(json.dumps(test_contexts, ensure_ascii=False, separators=(",", ":"))) <= remaining_budget:
                compact_contexts.append(ctx_entry)
                selected_passages.append(pid)
                selected_passage_aliases.append(p_alias)
            else:
                break

        payload = {
            "format": "direct-llm-compact-v1",
            "legend": {
                "tables": table_legend,
                "passages": passage_legend,
                "ids": "t=table, r=row, vals=column values, psg=linked passage IDs",
            },
            "rows": compact_rows,
            "contexts": compact_contexts,
        }
        compact_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

        prompt = f"""Answer the question using only the grounded compact table rows and passages below.

`rows` retains table rows with short table ID (`t`), row index (`r`), cell values (`vals`), and linked passage references (`psg`). `contexts` contains passages deduplicated by short ID (`id`). Use both table rows and passages to verify multi-hop facts. Copy the shortest answer span exactly as written in the evidence; do not translate or expand names. Return only that span.
{response_contract(source_label='a table row ID (`table_name:row_index`) or passage ID')}

Question: {example.question}

Compact evidence payload:
{compact_json}

Answer:"""

        trace = dict(retrieved.get("retrieval_trace", {}))
        trace.update(
            selected_table_row_indices=[b["row_index"] for b in selected_blocks],
            selected_table_row_ids=selected_row_ids,
            context_selection_policy="direct_llm_compact_serialization",
            table_context_budget_chars=table_budget,
            passage_context_budget_chars=remaining_budget,
        )

        id_aliases = {
            "tables": tables,
            "table_legend": table_legend,
            "passages": passages,
            "passage_legend": passage_legend,
            "row_alias_map": {
                f"{tables[b['table_name']]}:r{b['row_index']}": f"{b['table_name']}:{b['row_index']}"
                for b in selected_blocks
            },
        }

        return prompt, selected_row_ids, selected_passages, table_truncated, trace, id_aliases

    def run(self, example: DatasetExample) -> dict:
        prompt, row_ids, passage_ids, table_truncated, retrieval_trace, id_aliases = self.build_prompt(example)
        provider = get_provider()
        started = time.perf_counter()
        request_max_tokens = self._request_token_limit(provider, self.config.max_output_tokens)
        raw_answer = llm_call(prompt, max_tokens=request_max_tokens, temperature=self.config.temperature)

        # Allow both full IDs and compact alias IDs in response validation
        row_alias_map = id_aliases.get("row_alias_map", {})
        passage_legend = id_aliases.get("passage_legend", {})
        allowed_ids = set(row_ids) | set(passage_ids) | set(row_alias_map.keys()) | set(passage_legend.keys())

        parsed = parse_response(raw_answer, allowed_ids)
        answer = parsed["answer"]

        # Canonicalize cited context IDs back to standard full IDs
        canonical_cited = []
        for cid in parsed.get("evidence_context_ids", []):
            if cid in row_alias_map:
                canonical_cited.append(row_alias_map[cid])
            elif cid in passage_legend:
                canonical_cited.append(passage_legend[cid])
            else:
                canonical_cited.append(cid)

        return {
            "answer": answer,
            "method": self.method_name,
            "provider": provider.name,
            "model": getattr(provider, "model", None),
            "passage_top_k": self.config.passage_top_k,
            "retrieved_passage_ids": passage_ids,
            "table_truncated": table_truncated,
            "retrieval_trace": retrieval_trace,
            "prompt_chars": len(prompt),
            "max_context_chars": self.config.max_context_chars,
            "max_output_tokens": self.config.max_output_tokens,
            "request_max_output_tokens": request_max_tokens,
            "temperature": self.config.temperature,
            "answer_retry_attempted": False,
            "answer_response_valid": parsed["response_valid"],
            "abstained_for_missing_grounding": parsed["abstained"],
            "evidence_context_ids": canonical_cited,
            "grounding_diagnostic": parsed["diagnostic"],
            "raw_answer": self._bounded(raw_answer),
            "retry_raw_answer": None,
            "llm_calls": 1,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
