"""Entity-aware graph retrieval ablation without connected path reasoning."""

from __future__ import annotations

import json
import time

from src.baselines.rag_variants import RAGConfig
from src.datasets.schema import DatasetExample
from src.extraction.extractor import EntityRelationExtractor
from src.kg.builder import OnlineKGBuilder
from src.baselines.kg_payload import deduplicate_edge_contexts
from src.llm.client import get_provider, llm_call
from src.retrieval.coarse_retrieval import two_stage_retrieve


class GraphRetrievalNoPathBaseline:
    """Use entity-aware retrieval and a KG, but expose unconnected triples only."""

    method_name = "graph_retrieval_no_path"

    def __init__(self, config: RAGConfig | None = None):
        self.config = config or RAGConfig()
        self.config.validate()
        # Add deterministic rule-extracted text facts without a model call,
        # while retaining the original passage contexts for audit.
        self.kg_builder = OnlineKGBuilder(EntityRelationExtractor(
            temperature=self.config.temperature,
            max_output_tokens=self.config.max_output_tokens,
            use_llm_text_enrichment=False,
            use_rule_text_triples=self.config.use_rule_text_triples,
        ))

    @staticmethod
    def _request_token_limit(provider, configured: int) -> int:
        """Reserve completion budget when the provider uses hidden reasoning."""
        model = str(getattr(provider, "model", "")).casefold()
        needs_reasoning_budget = bool(getattr(provider, "reasoning_enabled", False))
        return max(configured, 512) if needs_reasoning_budget or "gpt-oss" in model else configured

    @staticmethod
    def _prompt_kg_payload(kg_edges: list[dict]) -> dict:
        """Keep all edge evidence while storing each passage once by source id."""
        return deduplicate_edge_contexts(kg_edges)

    @staticmethod
    def _bounded_prompt_kg_payload(kg_edges: list[dict], limit: int) -> tuple[dict, bool]:
        """Serialize an audit-preserving, valid KG view within the prompt budget.

        The unbounded graph remains in the returned run trace.  This view is
        deliberately an unordered edge set (so it does not introduce path
        reasoning), but only retains source contexts that fit alongside their
        linked edge records.  An edge can still be exposed without its context
        when its source text alone would exhaust the budget.
        """
        full_payload = GraphRetrievalNoPathBaseline._prompt_kg_payload(kg_edges)
        if len(json.dumps(full_payload, ensure_ascii=False, default=str)) <= limit:
            return full_payload, False

        all_contexts = full_payload["contexts_by_source_id"]
        bounded = {"edges": [], "contexts_by_source_id": {}}
        for edge in full_payload["edges"]:
            candidate = {
                "edges": [*bounded["edges"], edge],
                "contexts_by_source_id": dict(bounded["contexts_by_source_id"]),
            }
            for source_id in edge.get("context_ids", []):
                if source_id in all_contexts:
                    candidate["contexts_by_source_id"].setdefault(
                        source_id, all_contexts[source_id]
                    )
            if len(json.dumps(candidate, ensure_ascii=False, default=str)) <= limit:
                bounded = candidate
                continue

            # Retain the structural/semantic edge if it fits on its own, but
            # do not leave an unresolved context reference in the prompt.
            edge_without_context = dict(edge)
            edge_without_context.pop("context_ids", None)
            candidate = {
                "edges": [*bounded["edges"], edge_without_context],
                "contexts_by_source_id": dict(bounded["contexts_by_source_id"]),
            }
            if len(json.dumps(candidate, ensure_ascii=False, default=str)) <= limit:
                bounded = candidate

        return bounded, True

    def run(self, example: DatasetExample) -> dict:
        started = time.perf_counter()
        retrieved = two_stage_retrieve(
            example.question, example.table_rows, example.text_passages,
            example.web_snippets, top_k=self.config.top_k,
            second_stage_k=self.config.second_stage_k,
            max_table_rows=self.config.max_table_rows_for_kg,
        )
        kg = self.kg_builder.build(retrieved)
        kg_trace = kg.to_trace()
        semantic_kg_edges = kg_trace["edges"]
        # Match Path Text's table-to-KG view: semantic facts plus row-record
        # structure, including has_record, row field, and passage bridge edges.
        # Graph No Path still supplies an unordered set and performs no path
        # planning; it simply no longer discards the table structure.
        kg_edges = kg.path_edge_records()
        prompt_triples = [
            {"head": edge["head"], "relation": edge.get("relation"), "tail": edge["tail"]}
            for edge in kg_edges
        ][:200]
        # Preserve every KG edge attribute and all linked passage contexts in
        # the exact payload sent to the answer model, without repeating the
        # same passage for every linked table edge.
        prompt_kg_edges, prompt_truncated = self._bounded_prompt_kg_payload(
            kg_edges, self.config.max_context_chars
        )
        prompt_payload = json.dumps(prompt_kg_edges, ensure_ascii=False, default=str)
        prompt = f"""Answer using only these retrieved KG edge records. Records with `structural: true` preserve the table row/column topology; records with `structural: false` are semantic facts. Each record may reference text evidence through `context_ids`; resolve them in `contexts_by_source_id`. The records are an unordered set;
do not assume a reasoning path not supported by them. Return only the shortest answer span.

Question: {example.question}
KG payload: {prompt_payload}
Answer:"""
        provider = get_provider()
        request_max_tokens = self._request_token_limit(provider, self.config.max_output_tokens)
        answer = llm_call(prompt, max_tokens=request_max_tokens,
                          temperature=self.config.temperature).strip()
        retry_prompt = None
        if not answer:
            retry_prompt = prompt + """

Your previous response was empty. Return the shortest non-empty answer span now.
Answer:"""
            answer = llm_call(
                retry_prompt,
                max_tokens=request_max_tokens,
                temperature=self.config.temperature,
            ).strip()
        return {
            "answer": answer, "method": self.method_name, "provider": provider.name,
            "model": getattr(provider, "model", None), "kg_summary": kg.summary(),
            # Keep the complete KG and the exact answer-time payload for audit.
            "graph_kg_trace": kg_trace,
            "graph_semantic_kg_edges": semantic_kg_edges,
            "graph_kg_edges": kg_edges,
            "prompt_kg_edges": prompt_kg_edges,
            "prompt_triples": prompt_triples, "prompt": prompt,
            "entity_anchor": retrieved["retrieval_trace"].get("entity_anchor", {}),
            "retrieval_trace": retrieved["retrieval_trace"], "prompt_chars": len(prompt),
            "request_max_output_tokens": request_max_tokens,
            "prompt_context_budget_chars": self.config.max_context_chars,
            "prompt_context_truncated": prompt_truncated,
            "answer_retry_attempted": retry_prompt is not None,
            "retry_prompt": retry_prompt,
            "retry_prompt_chars": len(retry_prompt) if retry_prompt else 0,
            "llm_calls": 1, "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
