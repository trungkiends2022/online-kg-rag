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
                # This branch reasons directly over retrieved passage context.
                # It deliberately performs zero LLM text-triple extraction.
                use_llm_text_enrichment=False,
            )
        )
        self.planner = planner or GroundedPathPlanner()

    @staticmethod
    def _terms(value: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", str(value).casefold()))

    @staticmethod
    def _clip_text(value: str, question_terms: set[str], limit: int = 1_400) -> str:
        """Keep a small evidence excerpt, centered on a question term when possible."""
        value = str(value or "").strip()
        if len(value) <= limit:
            return value
        lowered = value.casefold()
        positions = [lowered.find(term) for term in question_terms if len(term) > 2]
        positions = [position for position in positions if position >= 0]
        if not positions:
            return value[: limit - 1].rstrip() + "…"
        start = max(min(positions) - limit // 3, 0)
        end = min(start + limit - 1, len(value))
        start = max(end - limit + 1, 0)
        prefix = "…" if start else ""
        suffix = "…" if end < len(value) else ""
        return prefix + value[start:end].strip() + suffix

    @staticmethod
    def _path_view(path: dict, rank: int) -> dict:
        """A path refers to evidence edges instead of duplicating them."""
        return {
            "path_id": path["path_id"],
            "rank": rank,
            "score": path.get("score", 0.0),
            "score_components": path.get("score_components", {}),
            "nodes": path.get("nodes", []),
            "edge_ids": [edge.get("edge_id") for edge in path.get("edges", [])],
            "steps": path.get("steps", []),
        }

    @staticmethod
    def _edge_view(edge: dict) -> dict:
        """Keep only the facts a final judge needs to verify a graph edge."""
        return {
            key: edge.get(key)
            for key in (
                "edge_id", "head", "relation", "tail", "source_type", "source_id",
                "row_index", "column_name", "header_path", "structural",
                "traversal_from", "traversal_to", "direction",
            )
            if edge.get(key) is not None
        }

    def _bounded_kg_context(
        self, question: str, path_records: list[dict], kg, retrieval_trace: dict,
    ) -> str:
        """Serialize Top-N path evidence before optional auxiliary KG facts."""
        question_terms = self._terms(question)
        path_terms = self._terms(" ".join(
            step["goal"] for path in path_records for step in path["steps"]
        ))
        candidate_entities = {
            str(entity).casefold()
            for constraint in retrieval_trace.get("table_constraints", [])
            for entity in constraint.get("candidates", [])
        }
        payload = {
            "table_constraints": retrieval_trace.get("table_constraints", []),
            "table_witnesses": retrieval_trace.get("table_witnesses", []),
            "reasoning_paths": [
                self._path_view(path, rank)
                for rank, path in enumerate(path_records, start=1)
            ],
            "kg_edges": [],
            "text_contexts": [],
        }

        # The judge must see every selected-path edge before it sees any auxiliary
        # edge. Paths only reference edge IDs, avoiding repeated context text.
        selected_edge_ids = set()
        for path in path_records:
            for edge in path.get("edges", []):
                edge_id = edge.get("edge_id")
                if edge_id in selected_edge_ids:
                    continue
                candidate = {
                    **payload,
                    "kg_edges": [*payload["kg_edges"], self._edge_view(edge)],
                }
                if len(json.dumps(candidate, ensure_ascii=False)) <= self.config.max_context_chars:
                    payload["kg_edges"].append(self._edge_view(edge))
                    selected_edge_ids.add(edge_id)

        path_source_ids = {
            str(edge.get("source_id"))
            for path in path_records for edge in path.get("edges", [])
        }
        context_ranked = []
        for context in kg.text_contexts.values():
            rendered = " ".join(
                str(context.get(field, "")) for field in ("context_before", "text")
            )
            compact_context = {
                key: value
                for key, value in dict(context).items()
                if key not in {"text", "context_before"}
            } | {
                "text": self._clip_text(rendered, question_terms),
            }
            context_ranked.append((
                10 if str(context.get("source_id")) in path_source_ids else 0,
                len(question_terms & self._terms(rendered))
                + len(path_terms & self._terms(rendered)),
                str(context.get("source_id", "")),
                compact_context,
            ))
        for _, _, _, context in sorted(
            context_ranked, key=lambda item: item[:3], reverse=True,
        ):
            candidate = {**payload, "text_contexts": [*payload["text_contexts"], context]}
            if len(json.dumps(candidate, ensure_ascii=False)) <= self.config.max_context_chars:
                payload["text_contexts"].append(context)

        ranked = []
        for index, edge in enumerate(kg.path_edge_records()):
            head, tail = edge["head"], edge["tail"]
            context_text = " ".join(
                str(context.get("text", "")) for context in edge.get("contexts", [])
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
            )
            ranked.append((score, -index, edge))
        for _, _, edge in sorted(ranked, key=lambda item: item[:2], reverse=True):
            if edge.get("edge_id") in selected_edge_ids:
                continue
            candidate = {
                **payload,
                "kg_edges": [*payload["kg_edges"], self._edge_view(edge)],
            }
            if len(json.dumps(candidate, ensure_ascii=False)) <= self.config.max_context_chars:
                payload["kg_edges"].append(self._edge_view(edge))
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _constraint_instruction(retrieval_trace: dict) -> str:
        policy = retrieval_trace.get("constraint_policy", {})
        candidates = policy.get("allowed_output_values", [])
        witnesses = retrieval_trace.get("table_witnesses", [])
        instruction = ""
        if witnesses:
            witness_summaries = []
            for w in witnesses:
                op = w.get("operator", "")
                entities = ", ".join(w.get("bridge_entities", ()))
                cols = ", ".join(w.get("evidence_columns", ()))
                witness_summaries.append(f"{op} on [{cols}] -> entity: {entities}")
            instruction += (
                "\nTABLE WITNESS EVIDENCE: The following entity was grounded by exact local table logic:\n"
                + "\n".join(f"- {s}" for s in witness_summaries)
                + "\nPrioritize this witness entity and its linked passage evidence.\n"
            )
        if candidates:
            instruction += (
                "\nBẮT BUỘC: câu hỏi có ràng buộc bảng. Đáp án phải là một trong các "
                f"candidate sau: {json.dumps(candidates, ensure_ascii=False)}. "
                "Chỉ chọn candidate khi evidence bao phủ cả điều kiện bảng lẫn điều kiện "
                "nêu trong text; không trả entity chỉ thỏa một vế.\n"
            )
        return instruction

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

    @staticmethod
    def _fallback_path_answer(path_record: dict) -> str:
        """Return the final grounded entity only when the final judge fails."""
        for edge in reversed(path_record.get("edges", [])):
            candidate = str(edge.get("traversal_to") or edge.get("tail") or "").strip()
            if not candidate or candidate.startswith(("table:", "passage:")):
                continue
            if re.fullmatch(r"\d+", candidate):
                continue
            return candidate
        return ""

    @staticmethod
    def _parse_final_judge_response(response: str) -> dict | None:
        """Parse JSON even when a provider wraps it in a Markdown fence."""
        response = str(response or "").strip()
        if response.startswith("```"):
            response = re.sub(r"^```(?:json)?\s*|\s*```$", "", response).strip()
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", response, flags=re.DOTALL)
            if not match:
                return None
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return parsed if isinstance(parsed, dict) else None

    def _reconcile_plain_answer(
        self,
        response: str,
        path_records: list[dict],
        retrieval_trace: dict,
    ) -> tuple[str, str | None, list[str]]:
        """Ground a plain answer in one ranked path for non-JSON providers."""
        response = str(response or "").strip()
        if not response:
            return "", None, []
        candidates = retrieval_trace.get("constraint_policy", {}).get(
            "allowed_output_values", []
        )
        normalized = response.casefold()
        matched_candidates = [
            candidate for candidate in candidates if candidate.casefold() in normalized
        ]
        if candidates:
            if len(matched_candidates) != 1:
                return "", None, []
            answer = matched_candidates[0]
        else:
            answer = response
        answer_normalized = answer.casefold().strip()
        for path in path_records:
            evidence_ids = []
            for edge in path.get("edges", []):
                values = [
                    str(edge.get(field, ""))
                    for field in ("traversal_to", "tail", "head", "traversal_from")
                ]
                values.extend(
                    str(context.get("text", "")) for context in edge.get("contexts", [])
                )
                if any(
                    value.casefold().strip() == answer_normalized
                    or answer_normalized in value.casefold()
                    for value in values if value
                ):
                    evidence_ids.append(str(edge.get("edge_id")))
            if evidence_ids:
                return answer, path["path_id"], list(dict.fromkeys(evidence_ids))
        return "", None, []

    def _validated_judgement(
        self,
        response: str,
        path_records: list[dict],
        retrieval_trace: dict,
    ) -> tuple[str, str | None, list[str], str | None, str | None]:
        """Return validated answer/path/evidence and the response format."""
        judgement = self._parse_final_judge_response(response)
        if judgement is None:
            answer, path_id, evidence_ids = self._reconcile_plain_answer(
                response, path_records, retrieval_trace,
            )
            if answer:
                return answer, path_id, evidence_ids, None, "plain_answer_reconciled"
            return "", None, [], "invalid_json_or_ungrounded_plain_answer", None
        path_id = judgement.get("selected_path_id")
        answer = judgement.get("answer")
        evidence_ids = judgement.get("evidence_edge_ids")
        paths_by_id = {path["path_id"]: path for path in path_records}
        if not isinstance(path_id, str) or path_id not in paths_by_id:
            return "", None, [], "unknown_path_id", "json"
        if not isinstance(answer, str) or not answer.strip():
            return "", None, [], "empty_answer", "json"
        if not isinstance(evidence_ids, list) or not evidence_ids or not all(
            isinstance(edge_id, str) for edge_id in evidence_ids
        ):
            return "", None, [], "missing_evidence_edge_ids", "json"
        path_edge_ids = {
            str(edge.get("edge_id")) for edge in paths_by_id[path_id].get("edges", [])
        }
        if not set(evidence_ids) <= path_edge_ids:
            return "", None, [], "evidence_outside_selected_path", "json"
        answer = self._canonicalize_candidate(answer.strip(), retrieval_trace)
        candidates = retrieval_trace.get("constraint_policy", {}).get(
            "allowed_output_values", []
        )
        if candidates and answer not in candidates:
            return "", None, [], "answer_outside_table_candidates", "json"
        return answer, path_id, evidence_ids, None, "json"

    def _final_judge_prompt(
        self,
        question: str,
        context: str,
        retrieval_trace: dict,
        *,
        retry: bool = False,
    ) -> str:
        retry_instruction = (
            "This is the only retry; use the single supplied path. "
            if retry else "Compare only the supplied candidate paths. "
        )
        return f"""You are the final grounded-path judge. {retry_instruction}
Use only the ranked Online KG paths and their supporting evidence below. Do not
invent facts, generate code, or execute a program. Prefer a path whose edges and
passage context jointly satisfy every condition in the question.
{self._constraint_instruction(retrieval_trace)}
Answer contract: {self._answer_shape_instruction(question)}

Return only the shortest answer span or numeric answer. Do not explain it and do
not return JSON.

Question: {question}

Online KG candidate payload:
{context}

Final answer:
"""

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
        prompt = self._final_judge_prompt(
            example.question, context, retrieval_trace,
        )
        provider = get_provider()
        raw_answer = llm_call(
            prompt,
            max_tokens=self.config.max_output_tokens,
            temperature=self.config.temperature,
        )
        answer, selected_path_id, evidence_edge_ids, validation_error, response_format = self._validated_judgement(
            raw_answer, path_records, retrieval_trace,
        )
        answer_retry_attempted = False
        answer_fallback_used = False
        retry_prompt_chars = 0
        if validation_error:
            answer_retry_attempted = True
            top_path = path_records[0]
            narrow_context = self._bounded_kg_context(
                example.question, [top_path], kg, retrieval_trace,
            )
            retry_prompt = self._final_judge_prompt(
                example.question, narrow_context, retrieval_trace, retry=True,
            )
            retry_prompt_chars = len(retry_prompt)
            raw_answer = llm_call(
                retry_prompt,
                max_tokens=min(128, self.config.max_output_tokens),
                temperature=self.config.temperature,
            )
            answer, selected_path_id, evidence_edge_ids, retry_error, response_format = self._validated_judgement(
                raw_answer, [top_path], retrieval_trace,
            )
            if retry_error:
                answer = self._fallback_path_answer(top_path)
                answer_fallback_used = bool(answer)
                validation_error = retry_error
            else:
                validation_error = None
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
            "answer_retry_attempted": answer_retry_attempted,
            "answer_fallback_used": answer_fallback_used,
            "retry_prompt_chars": retry_prompt_chars,
            "llm_selected_path_id": selected_path_id,
            "final_judge_evidence_edge_ids": evidence_edge_ids,
            "final_judge_response_format": response_format,
            "final_judge_valid": validation_error is None,
            "final_judge_failure_reason": validation_error,
            "kg_summary": kg.summary(),
            "entity_anchor": retrieval_trace.get("entity_anchor", {}),
            "retrieval_trace": retrieval_trace,
            "reasoning_paths": path_records,
            "best_path_id": path_records[0]["path_id"] if path_records else None,
            "best_path_score": path_records[0]["score"] if path_records else None,
            "execution_mode": "path_text",
            "code_generated": False,
            "program_executed": False,
            "text_extraction_mode": "direct_context_no_llm",
        }
