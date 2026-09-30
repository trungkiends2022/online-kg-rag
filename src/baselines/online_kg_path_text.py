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
                use_rule_text_triples=self.config.use_rule_text_triples,
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
            "path_verification": {
                key: path.get("path_verification", {}).get(key)
                for key in ("status", "selection_score", "hard_failures")
                if key in path.get("path_verification", {})
            },
        }

    @staticmethod
    def _edge_view(edge: dict) -> dict:
        """Keep only the facts a final judge needs to verify a graph edge."""
        return {
            key: edge.get(key)
            for key in (
                "edge_id", "head", "relation", "tail", "source_type", "source_id",
                "row_index", "column_name", "header_path", "structural",
                "source_group",
                "traversal_from", "traversal_to", "direction",
            )
            if edge.get(key) is not None
        }

    @staticmethod
    def _path_evidence_text(path: dict) -> str:
        return " ".join(
            " ".join(
                str(edge.get(field, ""))
                for field in ("head", "relation", "tail", "traversal_from", "traversal_to")
            ) + " " + " ".join(
                str(context.get(field, ""))
                for context in edge.get("contexts", [])
                for field in ("context_before", "text")
            )
            for edge in path.get("edges", [])
        )

    def _verify_path(
        self, question: str, path: dict, retrieval_trace: dict,
    ) -> dict:
        """Deterministically reject paths that miss mandatory table grounding."""
        edges = path.get("edges", [])
        path_text = self._path_evidence_text(path).casefold()
        question_terms = self._terms(question) - {
            "what", "which", "where", "when", "who", "whose", "how", "does",
            "did", "with", "from", "that", "this", "there", "their",
        }
        covered_terms = question_terms & self._terms(path_text)
        row_indices = {edge.get("row_index") for edge in edges if edge.get("row_index") is not None}
        nodes = {
            str(value).casefold()
            for edge in edges
            for value in (edge.get("head"), edge.get("tail"), edge.get("traversal_from"), edge.get("traversal_to"))
            if value is not None
        }
        witnesses = retrieval_trace.get("table_witnesses", [])
        matched_witnesses = []
        linked_witness = False
        for index, witness in enumerate(witnesses):
            witness_rows = set(witness.get("row_indices", ()))
            bridge_entities = {str(value).casefold() for value in witness.get("bridge_entities", ())}
            links = {
                str(value).removeprefix("/wiki/").removeprefix("passage:").casefold()
                for value in witness.get("hyperlinks", ()) if value
            }
            row_or_entity = bool(row_indices & witness_rows) or bool(nodes & bridge_entities)
            link_match = any(link and link in path_text for link in links)
            if row_or_entity:
                matched_witnesses.append(index)
            linked_witness = linked_witness or (row_or_entity and link_match)

        policy = retrieval_trace.get("constraint_policy", {})
        table_required = bool(policy.get("require_table_evidence"))
        table_grounded = bool(matched_witnesses) if witnesses else bool(row_indices)
        numeric_question = bool(re.search(r"\b(how many|how much|what year|which year|when)\b", question, re.I))
        numeric_evidence = bool(re.search(r"(?<!\d)\d[\d,]*(?:\.\d+)?", path_text))
        terminal = str(
            edges[-1].get("traversal_to") or edges[-1].get("tail") or ""
        ) if edges else ""
        terminal_is_container = terminal.startswith(("table:", "passage:"))
        hard_failures = []
        if not edges:
            hard_failures.append("no_grounded_edges")
        if table_required and not table_grounded:
            hard_failures.append("missing_table_witness")
        score = float(path.get("score", 0.0))
        score += 3.0 if table_grounded else 0.0
        score += 2.0 if linked_witness else 0.0
        score += min(len(covered_terms), 5) * 0.4
        if numeric_question:
            score += 1.5 if numeric_evidence else -1.5
        if terminal_is_container:
            score -= 1.0
        return {
            "status": "qualified" if not hard_failures else "rejected",
            "hard_failures": hard_failures,
            "question_term_coverage": round(
                len(covered_terms) / max(len(question_terms), 1), 4,
            ),
            "table_witness_indices": matched_witnesses,
            "linked_witness": linked_witness,
            "numeric_evidence": numeric_evidence if numeric_question else None,
            "terminal_is_container": terminal_is_container,
            "selection_score": round(score, 4),
        }

    def _select_verified_paths(
        self, question: str, path_records: list[dict], retrieval_trace: dict,
    ) -> tuple[list[dict], dict]:
        """Annotate retrieval paths; never choose or discard an answer path early.

        A path can be a useful bridge even when its last edge is a passage URL.
        The former implementation dropped such paths before the answer text was
        read, which made the model choose among several equally incomplete
        chains.  Verification remains an audit/ranking signal; final grounding
        is deliberately performed after answer synthesis.
        """
        for path in path_records:
            path["path_verification"] = self._verify_path(question, path, retrieval_trace)
        ordered = sorted(
            path_records,
            key=lambda path: (
                -path["path_verification"]["selection_score"],
                -float(path.get("score", 0.0)),
                path["path_id"],
            ),
        )
        qualified = [
            path for path in ordered
            if path["path_verification"]["status"] == "qualified"
        ]
        return ordered, {
            "candidate_path_ids": [path["path_id"] for path in ordered],
            "qualified_path_ids": [path["path_id"] for path in qualified],
            "rejected_path_ids": [
                path["path_id"] for path in ordered
                if path["path_verification"]["status"] == "rejected"
            ],
            "abstained_for_missing_grounding": not bool(ordered),
            "pre_answer_path_selection": False,
            "verification_by_path": {
                path["path_id"]: path["path_verification"] for path in ordered
            },
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
        """Expose table candidates as bridge evidence, never a blanket answer set."""
        policy = retrieval_trace.get("constraint_policy", {})
        candidates = policy.get("allowed_output_values", [])
        witnesses = retrieval_trace.get("table_witnesses", [])
        instruction = ""
        if witnesses:
            summaries = []
            for witness in witnesses:
                summaries.append(
                    f"{witness.get('operator', '')} on "
                    f"[{', '.join(witness.get('evidence_columns', ()))}] -> bridge entity: "
                    f"{', '.join(witness.get('bridge_entities', ()))}"
                )
            instruction += "\nTABLE WITNESS EVIDENCE:\n" + "\n".join(
                f"- {summary}" for summary in summaries
            ) + "\nUse these as bridge evidence; the requested answer may be a later text fact.\n"
        if candidates:
            instruction += (
                "\nTABLE CANDIDATES (bridge entities, not a mandatory answer list): "
                f"{json.dumps(candidates, ensure_ascii=False)}. "
                "Return one only when it is itself the final answer requested by the question.\n"
            )
        return instruction

    @staticmethod
    def _answer_shape_instruction(question: str) -> str:
        lowered = question.casefold()
        if "what year" in lowered or "which year" in lowered:
            return "Return the four-digit year from the final supported fact, not a related event year."
        if re.search(r"\bwhen\b", lowered):
            return "Return the most specific final date or date range supported by the final evidence."
        if "how many" in lowered or "how much" in lowered:
            return "Return the final grounded count or amount, not an intermediate value."
        return "Return the final entity/value supported by the complete evidence, not an intermediate entity."

    @staticmethod
    def _bounded_response(value: str | None, limit: int = 1_000) -> str:
        value = str(value or "").strip()
        return value if len(value) <= limit else value[: limit - 1] + "…"

    @staticmethod
    def _canonicalize_kg_alias(answer: str, kg) -> str:
        if not answer:
            return answer
        resolved = kg._resolve_entity(answer)
        aliases = [resolved]
        aliases.extend(alias for alias, canonical in kg.entity_aliases.items()
                       if kg._resolve_entity(canonical) == resolved)
        return min(aliases, key=lambda value: (len(str(value)), str(value).casefold()))

    @staticmethod
    def _canonicalize_candidate(answer: str, retrieval_trace: dict) -> str:
        """Canonicalize table values only when the trace explicitly requires it."""
        policy = retrieval_trace.get("constraint_policy", {})
        if not policy.get("enforce_answer_candidate", False):
            return answer
        candidates = policy.get("allowed_output_values", [])
        normalized = answer.casefold().strip()
        exact = [candidate for candidate in candidates if candidate.casefold() == normalized]
        if exact:
            return exact[0]
        contained = [candidate for candidate in candidates if candidate.casefold() in normalized]
        return contained[0] if len(contained) == 1 else answer

    @staticmethod
    def _parse_final_judge_response(response: str) -> dict | None:
        """Accept exactly one JSON object, optionally wrapped in a JSON fence."""
        response = str(response or "").strip()
        if response.startswith("```"):
            response = re.sub(r"^```(?:json)?\s*|\s*```$", "", response).strip()
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _answer_match_score(question: str, answer: str, edge: dict) -> float:
        """Score an existing edge by how directly it supports a fixed answer."""
        answer = str(answer or "").strip()
        if not answer:
            return 0.0
        answer_key = " ".join(re.findall(r"[a-z0-9]+", answer.casefold()))
        answer_digits = re.sub(r"\D", "", answer)
        if not answer_key:
            return 0.0
        phrase = re.compile(r"(?<![a-z0-9])" + re.escape(answer_key) + r"(?![a-z0-9])")
        fields = " ".join(str(edge.get(field, "")) for field in (
            "head", "relation", "tail", "traversal_from", "traversal_to",
        ))
        field_key = " ".join(re.findall(r"[a-z0-9]+", fields.casefold()))
        contexts = " ".join(
            str(context.get(field, ""))
            for context in edge.get("contexts", [])
            for field in ("context_before", "text")
        )
        context_key = " ".join(re.findall(r"[a-z0-9]+", contexts.casefold()))
        score = 0.0
        if phrase.search(field_key):
            score += 100.0
        if phrase.search(context_key):
            score += 80.0
        if answer_digits:
            if answer_digits in re.sub(r"\D", "", fields):
                score += 100.0
            if answer_digits in re.sub(r"\D", "", contexts):
                score += 80.0
        if answer_digits and str(edge.get("relation", "")).casefold() in {"population", "count", "total"}:
            score += 25.0
        question_terms = OnlineKGPathTextBaseline._terms(question)
        score += min(len(question_terms & OnlineKGPathTextBaseline._terms(fields + " " + contexts)), 6) * 0.5
        return score

    def _materialize_answer_evidence_paths(
        self, question: str, answer: str, kg, path_records: list[dict],
    ) -> list[dict]:
        """Add answer-bearing KG edges only after free answer synthesis.

        The retrieval paths remain untouched in step 1.  These one-edge paths
        are created solely for reverse grounding when an answer fact was in the
        merged subgraph but not part of a top-k traversal.
        """
        existing = {
            str(edge.get("edge_id"))
            for path in path_records for edge in path.get("edges", [])
        }
        additions = []
        candidates = []
        for edge in kg.path_edge_records():
            if str(edge.get("edge_id")) in existing:
                continue
            score = self._answer_match_score(question, answer, edge)
            if score >= 80.0:
                candidates.append((score, edge))
        for rank, (score, edge) in enumerate(sorted(candidates, key=lambda item: (-item[0], str(item[1].get("edge_id"))))[:3], start=1):
            path_id = "answer_evidence_" + re.sub(r"[^a-zA-Z0-9_]+", "_", str(edge["edge_id"]))
            additions.append({
                "path_id": path_id,
                "score": score,
                "score_components": {"reverse_answer_match": round(score, 4)},
                "nodes": [str(edge["head"]), str(edge["tail"])],
                "edges": [edge],
                "steps": [{"step": 1, "goal": f'{edge["head"]} --{edge["relation"]}--> {edge["tail"]}', "depends_on": None}],
                "path_verification": {"status": "answer_evidence", "selection_score": score, "hard_failures": []},
                "created_after_answer": True,
            })
        return [*path_records, *additions]

    def _reverse_ground_answer(self, question: str, answer: str, path_records: list[dict]) -> tuple[list[str], list[str], dict]:
        """Map a completed answer to nearest real evidence without another LLM call."""
        scored = []
        for path in path_records:
            for edge in path.get("edges", []):
                score = self._answer_match_score(question, answer, edge)
                if score > 0:
                    scored.append((score, path["path_id"], str(edge.get("edge_id"))))
        if not scored:
            return [], [], {"status": "ungrounded", "reason": "answer_not_found_in_merged_evidence"}
        best = max(score for score, _, _ in scored)
        # Keep all exact/direct evidence ties; avoid attributing the answer to
        # merely adjacent paths whose text did not contain the answer span.
        selected = [(score, path_id, edge_id) for score, path_id, edge_id in scored if score >= max(80.0, best - 0.01)]
        if not selected:
            return [], [], {
                "status": "ungrounded",
                "reason": "answer_match_below_grounding_threshold",
                "best_score": round(best, 4),
            }
        path_ids = list(dict.fromkeys(path_id for _, path_id, _ in selected))
        edge_ids = list(dict.fromkeys(edge_id for _, _, edge_id in selected))
        return path_ids, edge_ids, {
            "status": "grounded",
            "mode": "deterministic_reverse_answer_match",
            "best_score": round(best, 4),
            "matched_edge_count": len(edge_ids),
        }

    def _answer_synthesis_prompt(self, question: str, context: str, retrieval_trace: dict, *, retry: bool = False) -> str:
        retry_instruction = "Your previous answer was invalid. " if retry else ""
        return f"""You are an evidence synthesizer. {retry_instruction}Use only the merged Online KG
subgraph and its related text contexts below. Do not select paths or citations yet:
first determine the final answer from the union of this evidence. Table values may
be bridge entities, and a linked-passage context can contain the final fact.
{self._constraint_instruction(retrieval_trace)}
Answer contract: {self._answer_shape_instruction(question)}
Return exactly one non-empty answer span on one line, with no JSON, label, explanation,
or chain-of-thought.

Question: {question}

Online KG candidate payload:
{context}

Final answer:"""

    def _synthesized_answer(self, response: str) -> str:
        """Accept a short answer, and tolerate a legacy JSON answer completion."""
        response = str(response or "").strip()
        parsed = self._parse_final_judge_response(response)
        if parsed and isinstance(parsed.get("answer"), str):
            response = parsed["answer"].strip()
        response = re.sub(r"^(?:final\s+)?answer\s*:\s*", "", response, flags=re.I)
        response = response.splitlines()[0].strip() if response else ""
        if response.casefold() in {"", "unknown", "n/a", "na", "null", "none", "insufficient information"}:
            return ""
        return response

    @staticmethod
    def _request_token_limit(provider, configured: int) -> int:
        """Reserve enough GPT-OSS completion budget for its hidden reasoning."""
        model = str(getattr(provider, "model", "")).casefold()
        return max(configured, 512) if "gpt-oss" in model else configured

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
        path_records, path_selection_audit = self._select_verified_paths(
            example.question, path_records, retrieval_trace,
        )
        if not path_records:
            return {
                "answer": None,
                "error": "No candidate path passed deterministic grounding checks.",
                "method": self.method_name,
                "kg_summary": kg.summary(),
                "entity_anchor": retrieval_trace.get("entity_anchor", {}),
                "retrieval_trace": retrieval_trace,
                "path_selection_audit": path_selection_audit,
                "reasoning_paths": [],
                "execution_mode": "path_text",
                "code_generated": False,
                "program_executed": False,
            }
        context = self._bounded_kg_context(example.question, path_records, kg, retrieval_trace)
        provider = get_provider()
        request_max_tokens = self._request_token_limit(provider, self.config.max_output_tokens)

        synthesis_prompt = self._answer_synthesis_prompt(example.question, context, retrieval_trace)
        raw_synthesis_response = llm_call(
            synthesis_prompt, max_tokens=request_max_tokens, temperature=self.config.temperature,
        )
        answer = self._synthesized_answer(raw_synthesis_response)
        synthesis_retry_attempted = False
        if not answer:
            synthesis_retry_attempted = True
            raw_synthesis_response = llm_call(
                self._answer_synthesis_prompt(example.question, context, retrieval_trace, retry=True),
                max_tokens=max(512, request_max_tokens), temperature=self.config.temperature,
            )
            answer = self._synthesized_answer(raw_synthesis_response)
        answer = self._canonicalize_kg_alias(answer, kg)
        answer = self._canonicalize_candidate(answer, retrieval_trace)

        # Step 3 is deliberately non-generative: after the answer exists,
        # attach it to exact answer-bearing edges/contexts in the merged KG.
        path_records = self._materialize_answer_evidence_paths(
            example.question, answer, kg, path_records,
        ) if answer else path_records
        selected_path_ids, evidence_edge_ids, grounding_audit = self._reverse_ground_answer(
            example.question, answer, path_records,
        ) if answer else ([], [], {"status": "ungrounded", "reason": "empty_synthesis_answer"})
        validation_error = None if evidence_edge_ids else grounding_audit["reason"]

        return {
            "answer": answer,
            "method": self.method_name,
            "provider": provider.name,
            "model": getattr(provider, "model", None),
            "temperature": self.config.temperature,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "prompt_chars": len(synthesis_prompt),
            "synthesis_prompt_chars": len(synthesis_prompt),
            "grounding_prompt_chars": 0,
            "synthesis_retry_attempted": synthesis_retry_attempted,
            "raw_synthesis_response": self._bounded_response(raw_synthesis_response),
            "request_max_output_tokens": request_max_tokens,
            "answer_retry_attempted": False,
            "answer_fallback_used": False,
            "retry_prompt_chars": 0,
            "raw_final_judge_response": None,
            "retry_raw_final_judge_response": None,
            "llm_selected_path_ids": selected_path_ids,
            "llm_selected_path_id": selected_path_ids[0] if selected_path_ids else None,
            "final_judge_evidence_edge_ids": evidence_edge_ids,
            "final_judge_response_format": "deterministic_reverse_grounding",
            "final_judge_valid": validation_error is None,
            "final_judge_failure_reason": validation_error,
            "grounding_audit": grounding_audit,
            "kg_summary": kg.summary(),
            "entity_anchor": retrieval_trace.get("entity_anchor", {}),
            "retrieval_trace": retrieval_trace,
            "path_selection_audit": path_selection_audit,
            "reasoning_paths": path_records,
            "best_path_id": path_records[0]["path_id"] if path_records else None,
            "best_path_score": path_records[0]["score"] if path_records else None,
            "execution_mode": "path_text",
            "code_generated": False,
            "program_executed": False,
            "text_extraction_mode": "direct_context_no_llm",
        }
