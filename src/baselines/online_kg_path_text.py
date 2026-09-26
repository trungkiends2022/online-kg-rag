"""Online-KG ablation that verbalizes paths and never executes a program."""

from __future__ import annotations

import json
import re
import time

from src.baselines.rag_variants import RAGConfig
from src.datasets.schema import DatasetExample
from src.extraction.extractor import EntityRelationExtractor
from src.kg.builder import OnlineKGBuilder
from src.llm.client import get_provider, llm_call
from src.planning.grounded_paths import GroundedPathPlanner
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
            EntityRelationExtractor(
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_output_tokens,
            )
        )
        self.planner = planner or GroundedPathPlanner()

    @staticmethod
    def _terms(value: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", str(value).casefold()))

    def _bounded_kg_context(
        self, question: str, path_records: list[dict], kg, retrieval_trace: dict,
    ) -> str:
        """Serialize the most useful edges instead of truncating insertion order.

        A KG often contains hundreds of edges.  The former ``context[:limit]``
        silently favoured early table rows and could discard the text edge that
        completes a multi-hop chain.  This deterministic ranker prioritizes
        question/path overlap and table-derived constraint candidates, while
        preserving a valid JSON payload within the context budget.
        """
        question_terms = self._terms(question)
        path_terms = self._terms(" ".join(
            step["goal"] for path in path_records for step in path["steps"]
        ))
        candidate_entities = {
            str(entity).casefold()
            for constraint in retrieval_trace.get("table_constraints", [])
            for entity in constraint.get("candidates", [])
        }
        ranked = []
        selected_edge_ids = {
            edge.get("edge_id")
            for path in path_records
            for edge in path.get("edges", [])
        }
        for index, edge in enumerate(kg.path_edge_records()):
            head, tail = edge["head"], edge["tail"]
            context_text = " ".join(
                str(context.get("text", ""))
                for context in edge.get("contexts", [])
            )
            rendered = f"{head} {edge.get('relation', '')} {tail} {context_text}"
            edge_terms = self._terms(rendered)
            candidate_bonus = 6 if (
                str(head).casefold() in candidate_entities
                or str(tail).casefold() in candidate_entities
            ) else 0
            score = (
                4 * len(question_terms & edge_terms)
                + 2 * len(path_terms & edge_terms)
                + candidate_bonus
                + (12 if edge.get("edge_id") in selected_edge_ids else 0)
            )
            ranked.append((score, -index, {
                "edge_id": edge.get("edge_id"),
                "head": head,
                "relation": edge.get("relation"),
                "tail": tail,
                "source_type": edge.get("source_type"),
                "source_id": edge.get("source_id"),
                "row_index": edge.get("row_index"),
                "column_name": edge.get("column_name"),
                "header_path": edge.get("header_path"),
                "structural": bool(edge.get("structural")),
                "contexts": edge.get("contexts", []),
            }))
        ranked.sort(key=lambda item: item[:2], reverse=True)
        payload = {
            "table_constraints": retrieval_trace.get("table_constraints", []),
            "reasoning_paths": path_records,
            "kg_edges": [],
        }
        for _, _, edge in ranked:
            candidate = {**payload, "kg_edges": [*payload["kg_edges"], edge]}
            if len(json.dumps(candidate, ensure_ascii=False)) > self.config.max_context_chars:
                continue
            payload["kg_edges"].append(edge)
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _constraint_instruction(retrieval_trace: dict) -> str:
        policy = retrieval_trace.get("constraint_policy", {})
        candidates = policy.get("allowed_output_values", [])
        if not candidates:
            return ""
        return (
            "\nBẮT BUỘC: câu hỏi có ràng buộc bảng. Đáp án phải là một trong các "
            f"candidate sau: {json.dumps(candidates, ensure_ascii=False)}. "
            "Chỉ chọn candidate khi evidence bao phủ cả điều kiện bảng lẫn điều kiện "
            "nêu trong text; không trả entity chỉ thỏa một vế.\n"
        )

    @staticmethod
    def _answer_shape_instruction(question: str) -> str:
        lowered = question.casefold()
        if "what year" in lowered or "which year" in lowered:
            return "Return the four-digit year from the final supported fact, not a related event year."
        if re.search(r"\bwhen\b", lowered):
            return (
                "Return the most specific final date or date range supported by the final edge; "
                "do not replace it with a broader event year."
            )
        if "how many" in lowered or "how much" in lowered:
            return "Return the final grounded count or amount, not an intermediate count or value."
        return "Return the final entity/value at the end of the complete supported chain, not an intermediate entity."

    @staticmethod
    def _canonicalize_kg_alias(answer: str, kg) -> str:
        """Use the shortest observed alias for the same resolved KG entity."""
        if not answer:
            return answer
        resolved = kg._resolve_entity(answer)
        aliases = [resolved]
        aliases.extend(
            alias for alias, canonical in kg.entity_aliases.items()
            if kg._resolve_entity(canonical) == resolved
        )
        return min(aliases, key=lambda value: (len(str(value)), str(value).casefold()))

    @staticmethod
    def _canonicalize_candidate(answer: str, retrieval_trace: dict) -> str:
        """Keep an exact table candidate when the model wraps it in prose."""
        candidates = retrieval_trace.get("constraint_policy", {}).get(
            "allowed_output_values", []
        )
        normalized = answer.casefold().strip()
        exact = [candidate for candidate in candidates if candidate.casefold() == normalized]
        if exact:
            return exact[0]
        contained = [candidate for candidate in candidates if candidate.casefold() in normalized]
        return contained[0] if len(contained) == 1 else answer

    def run(self, example: DatasetExample) -> dict:
        started = time.perf_counter()
        retrieved = two_stage_retrieve(
            example.question,
            example.table_rows,
            example.text_passages,
            example.web_snippets,
            top_k=self.config.top_k,
            second_stage_k=self.config.second_stage_k,
        )
        kg = self.kg_builder.build(retrieved)
        if kg.is_empty():
            return {
                "answer": None,
                "error": "Online KG is empty after retrieval.",
                "method": self.method_name,
                "kg_summary": kg.summary(),
            }
        retrieval_trace = retrieved.get("retrieval_trace", {})
        paths = self.planner.generate_candidates(
            example.question, kg, n=self.n_paths, constraint_context=retrieval_trace,
        )
        if not paths:
            return {
                "answer": None,
                "error": "No grounded text path could be generated.",
                "method": self.method_name,
                "kg_summary": kg.summary(),
                "entity_anchor": retrieval_trace.get("entity_anchor", {}),
                "retrieval_trace": retrieval_trace,
                "reasoning_paths": [],
                "execution_mode": "path_text",
                "code_generated": False,
                "program_executed": False,
            }
        path_records = [
            {
                "path_id": path.path_id,
                "score": getattr(path, "score", 0.0),
                "score_components": getattr(path, "score_components", {}),
                "nodes": getattr(path, "nodes", []),
                "edges": getattr(path, "edges", []),
                "steps": [
                    {"step": step.step, "goal": step.goal, "depends_on": step.depends_on}
                    for step in path.steps
                ],
            }
            for path in paths
        ]
        context = self._bounded_kg_context(
            example.question, path_records, kg, retrieval_trace,
        )
        prompt = f"""Answer the question using only the ranked, grounded Online KG
paths and supporting edges below. Every explicit path edge exists in the local
graph; a goal without explicit edges is only a proposal and must be checked
against the supporting edges. Reason over the paths as text. Do not generate
or execute Python, JSON IR, or any other program. Return only the shortest answer
span or numeric answer, without explanation.
{self._constraint_instruction(retrieval_trace)}
Answer contract: {self._answer_shape_instruction(example.question)}

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
        answer = self._canonicalize_kg_alias(answer, kg)
        answer = self._canonicalize_candidate(answer, retrieval_trace)
        return {
            "answer": answer,
            "method": self.method_name,
            "provider": provider.name,
            "model": getattr(provider, "model", None),
            "temperature": self.config.temperature,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "prompt_chars": len(prompt),
            "kg_summary": kg.summary(),
            "entity_anchor": retrieval_trace.get("entity_anchor", {}),
            "retrieval_trace": retrieval_trace,
            "reasoning_paths": path_records,
            "best_path_id": path_records[0]["path_id"] if path_records else None,
            "best_path_score": path_records[0]["score"] if path_records else None,
            "execution_mode": "path_text",
            "code_generated": False,
            "program_executed": False,
        }
