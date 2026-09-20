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
        self.kg_builder = OnlineKGBuilder(EntityRelationExtractor(temperature=self.config.temperature))

    def run(self, example: DatasetExample) -> dict:
        started = time.perf_counter()
        retrieved = two_stage_retrieve(example.question, example.table_rows, example.text_passages,
                                       example.web_snippets, top_k=self.config.top_k, second_stage_k=3)
        kg = self.kg_builder.build(retrieved)
        triples = [
            {"head": h, "relation": d.get("relation"), "tail": t}
            for h, t, d in kg.graph.edges(data=True)
        ][:200]
        prompt = f"""Answer using only these retrieved KG triples. The triples are an unordered set;
do not assume a reasoning path not supported by them. Return only the shortest answer span.

Question: {example.question}
Triples: {json.dumps(triples, ensure_ascii=False)}
Answer:"""
        provider = get_provider()
        answer = llm_call(prompt, max_tokens=self.config.max_output_tokens,
                          temperature=self.config.temperature).strip()
        return {
            "answer": answer, "method": self.method_name, "provider": provider.name,
            "model": getattr(provider, "model", None), "kg_summary": kg.summary(),
            "entity_anchor": retrieved["retrieval_trace"].get("entity_anchor", {}),
            "retrieval_trace": retrieved["retrieval_trace"], "prompt_chars": len(prompt),
            "llm_calls": 1, "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }
