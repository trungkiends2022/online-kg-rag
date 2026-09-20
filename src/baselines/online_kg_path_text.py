"""Online-KG ablation that verbalizes paths and never executes a program."""

from __future__ import annotations

import json
import time

from src.baselines.rag_variants import RAGConfig
from src.datasets.schema import DatasetExample
from src.extraction.extractor import EntityRelationExtractor
from src.kg.builder import OnlineKGBuilder
from src.llm.client import get_provider, llm_call
from src.planning.planner import PathPlanner
from src.retrieval.coarse_retrieval import two_stage_retrieve


class OnlineKGPathTextBaseline:
    """Keep retrieval/KG/planning, replace executable code with direct text QA."""

    method_name = "online_kg_path_text"

    def __init__(
        self,
        config: RAGConfig | None = None,
        *,
        n_paths: int = 5,
        kg_builder=None,
        planner=None,
    ):
        self.config = config or RAGConfig()
        self.config.validate()
        if n_paths < 1:
            raise ValueError("n_paths must be positive")
        self.n_paths = n_paths
        self.kg_builder = kg_builder or OnlineKGBuilder(
            EntityRelationExtractor(temperature=self.config.temperature)
        )
        self.planner = planner or PathPlanner(temperature=self.config.temperature)

    def run(self, example: DatasetExample) -> dict:
        started = time.perf_counter()
        retrieved = two_stage_retrieve(
            example.question,
            example.table_rows,
            example.text_passages,
            example.web_snippets,
            top_k=self.config.top_k,
            second_stage_k=3,
        )
        kg = self.kg_builder.build(retrieved)
        if kg.is_empty():
            return {
                "answer": None,
                "error": "Online KG is empty after retrieval.",
                "method": self.method_name,
                "kg_summary": kg.summary(),
            }
        paths = self.planner.generate_candidates(example.question, kg, n=self.n_paths)
        path_records = [
            {
                "path_id": path.path_id,
                "steps": [
                    {"step": step.step, "goal": step.goal, "depends_on": step.depends_on}
                    for step in path.steps
                ],
            }
            for path in paths
        ]
        edge_records = []
        for head, tail, data in kg.graph.edges(data=True):
            provenance = data.get("provenance")
            edge_records.append({
                "head": head,
                "relation": data.get("relation"),
                "tail": tail,
                "source_type": getattr(provenance, "source_type", None),
                "source_id": getattr(provenance, "source_id", None),
            })
        context = json.dumps(
            {"reasoning_paths": path_records, "kg_edges": edge_records},
            ensure_ascii=False,
        )
        context = context[: self.config.max_context_chars]
        prompt = f"""Answer the question using only the Online KG edges and the
proposed reasoning paths below. Reason over the paths as text. Do not generate
or execute Python, JSON IR, or any other program. Return only the shortest answer
span or numeric answer, without explanation.

Question: {example.question}

Online KG and reasoning paths:
{context}

Answer:"""
        provider = get_provider()
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
            "temperature": self.config.temperature,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "prompt_chars": len(prompt),
            "kg_summary": kg.summary(),
            "entity_anchor": retrieved.get("retrieval_trace", {}).get("entity_anchor", {}),
            "retrieval_trace": retrieved.get("retrieval_trace", {}),
            "reasoning_paths": path_records,
            "execution_mode": "path_text",
            "code_generated": False,
            "program_executed": False,
        }
