"""Entity-aware graph retrieval ablation without connected path reasoning."""

from __future__ import annotations

import json
import time

from src.baselines.rag_variants import RAGConfig
from src.datasets.schema import DatasetExample
from src.extraction.extractor import EntityRelationExtractor
from src.kg.builder import OnlineKGBuilder
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
        """Move repeated passage text into a source-id keyed context registry.

        The full KG trace keeps per-edge contexts for review. The answer prompt
        carries each passage only once and each edge references it through
        ``context_ids``. This preserves all evidence while avoiding repeated
        table-to-passage links from multiplying the same text in the request.
        """
        contexts_by_source_id: dict[str, dict] = {}
        edges: list[dict] = []
        for edge in kg_edges:
            prompt_edge = {
                key: value for key, value in edge.items() if key != "contexts"
            }
            context_ids: list[str] = []
            for context in edge.get("contexts", []):
                source_id = str(context.get("source_id", "")).strip()
                if not source_id:
                    continue
                contexts_by_source_id.setdefault(source_id, dict(context))
                if source_id not in context_ids:
                    context_ids.append(source_id)
            prompt_edge["context_ids"] = context_ids
            edges.append(prompt_edge)
        return {
            "edges": edges,
            "contexts_by_source_id": contexts_by_source_id,
        }

    def run(self, example: DatasetExample) -> dict:
        started = time.perf_counter()
        retrieved = two_stage_retrieve(example.question, example.table_rows, example.text_passages,
                                       example.web_snippets, top_k=self.config.top_k, second_stage_k=3)
        kg = self.kg_builder.build(retrieved)
        kg_edges = kg.to_trace()["edges"]
        prompt_triples = [
            {"head": h, "relation": d.get("relation"), "tail": t}
            for h, t, d in kg.graph.edges(data=True)
        ][:200]
        # Preserve every KG edge attribute and all linked passage contexts in
        # the exact payload sent to the answer model, without repeating the
        # same passage for every linked table edge.
        prompt_kg_edges = self._prompt_kg_payload(kg_edges)
        prompt_payload = json.dumps(prompt_kg_edges, ensure_ascii=False, default=str)
        prompt = f"""Answer using only these retrieved KG edge records. Each record may reference text evidence through `context_ids`; resolve them in `contexts_by_source_id`. The records are an unordered set;
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
            # Keep the exact answer-time evidence for auditable single-case reruns.
            "graph_kg_edges": kg_edges, "prompt_kg_edges": prompt_kg_edges,
            "prompt_triples": prompt_triples, "prompt": prompt,
            "entity_anchor": retrieved["retrieval_trace"].get("entity_anchor", {}),
            "retrieval_trace": retrieved["retrieval_trace"], "prompt_chars": len(prompt),
            "request_max_output_tokens": request_max_tokens,
            "answer_retry_attempted": retry_prompt is not None,
            "retry_prompt": retry_prompt,
            "retry_prompt_chars": len(retry_prompt) if retry_prompt else 0,
            "llm_calls": 1, "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
