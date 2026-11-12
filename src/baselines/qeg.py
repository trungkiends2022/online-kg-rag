"""Query Evidence Graph (QEG): evidence-path constrained OUEG reasoning."""

from __future__ import annotations

import json
import re
import time
from dataclasses import replace

from src.baselines.online_unified_evidence_graph import OnlineUnifiedEvidenceGraphBaseline
from src.baselines.oueg_prompt_compression import CompactOUEGPromptBuilder, OUEGPromptCompressionConfig
from src.baselines.rag_variants import RAGConfig
from src.baselines.ecar import EvidenceConstrainedAnswerRecovery
from src.llm.client import llm_call


class _QEGPromptBuilder(CompactOUEGPromptBuilder):
    """Compact full-graph reader prompt with a machine-auditable answer path."""

    def prompt(self, *, question: str, compact_json: str, tie_break_hint: str = "") -> str:
        return f"""Answer the question using the grounded compact QEG payload.

The full graph is available in `rows`, `edges`, and `contexts`. Do not infer facts
outside it. Every successful answer must cite a visible evidence path containing at
least one edge ID. Passage IDs are optional but should be cited for text evidence.

Return exactly:
FINAL_ANSWER: <shortest answer span copied from evidence>
EVIDENCE_PATH: {{\"edges\":[\"e...\"],\"passages\":[\"p...\"]}}

If no answer can be proved with visible edge IDs, return the prescribed NEED_FOCUS
or UNRESOLVED diagnostic instead. Scores, if present, are not evidence.{tie_break_hint}

Question: {question}
Compact QEG payload: {compact_json}
Answer:"""


class _QEGPathBalancePromptBuilder(CompactOUEGPromptBuilder):
    """Serialize many paths as neutral, stable evidence indices.

    The full OUEG graph remains available.  This experimental presentation
    removes the score/order channel that can anchor a reader on an early path,
    while retaining every row bundle and generated path as navigation aids.
    """

    def build(self, **kwargs) -> dict:
        paths = list(kwargs.get("suggested_paths") or [])
        # Every path survives.  Only their display order becomes independent
        # of the retrieval heuristic, with row bundles first in table order.
        neutral_paths = sorted(
            paths,
            key=lambda path: (
                0 if path.get("path_kind") == "row_bundle" else 1,
                str(path.get("row_id") or ""),
                str(path.get("anchor_entity") or ""),
                str(path.get("bridge_entity") or ""),
                str(path.get("path_id") or ""),
            ),
        )
        kwargs["suggested_paths"] = neutral_paths
        kwargs["ordering_hint"] = {
            "policy": "unranked_candidate_balanced",
            "note": (
                "Paths are stable evidence indices. No path is recommended, "
                "and rows must be checked directly for ordering constraints."
            ),
        }
        # Candidate score/lexical fields are another form of implicit path
        # ranking.  Preserve only whether structural ambiguity exists.
        ambiguity = kwargs.get("ambiguity") or {}
        kwargs["ambiguity"] = {
            "is_ambiguous": bool(ambiguity.get("is_ambiguous")),
            "status": "unranked_candidate_packets",
            "groups": [],
            "selective_prediction": {},
        }
        built = super().build(**kwargs)
        for path in built["payload"].get("paths", []):
            path.pop("score", None)
            path.pop("lex", None)
        built["json"] = json.dumps(
            built["payload"], ensure_ascii=False, separators=(",", ":"), default=str,
        )
        built["stats"]["prompt_payload_chars"] = len(built["json"])
        return built

    def prompt(self, *, question: str, compact_json: str, tie_break_hint: str = "") -> str:
        return f"""Answer the question using the grounded compact QEG payload.

`rows`, `edges`, and `contexts` contain the complete evidence graph. `paths`
are unranked evidence indices grouped in stable record order: none is a
recommended answer, and every relation, rank, and ordering claim must be
checked directly against the complete payload. Compare competing row packets
symmetrically. Copy the shortest answer span exactly as written in evidence.
Return only that span.{tie_break_hint}

Question: {question}
Compact QEG payload: {compact_json}
Answer:"""


class QueryEvidenceGraphBaseline(OnlineUnifiedEvidenceGraphBaseline):
    """Full-graph L1 plus evidence-path-constrained L1/L2 answer acceptance.

    QEG deliberately starts from the stronger no-path-guidance reader.  Paths
    appear only as model-selected, auditable evidence references in a successful
    answer, or as focused candidate packets during L2 recovery.
    """

    method_name = "qeg"

    def __init__(self, config: RAGConfig | None = None, *, kg_builder=None, prompt_builder=None):
        qeg_config = replace(
            config or RAGConfig(),
            use_path_guidance=False,
            use_path_focused_prompt=False,
            use_adaptive_verification=True,
            require_evidence_path=True,
        )
        builder = prompt_builder or _QEGPromptBuilder(OUEGPromptCompressionConfig(
            context_mode=qeg_config.oueg_context_mode,
            include_lexical_tiebreak=qeg_config.use_lexical_tiebreak,
        ))
        super().__init__(qeg_config, kg_builder=kg_builder, prompt_builder=builder)

    @staticmethod
    def _verification_prompt(question: str, compact_json: str, handoff: dict, *, mode: str) -> str:
        evidence_label = "L2 state capsule" if mode == "delta_only" else "complete QEG payload"
        return f"""Resolve the question using only the grounded {evidence_label} below.

The first reader could not supply a valid evidence path. Compare the focus
candidates against their table bindings and linked text. Do not use facts outside
this request. A successful answer must cite at least one visible edge ID.

Return exactly:
FINAL_ANSWER: <shortest answer span copied from evidence>
EVIDENCE_PATH: {{\"edges\":[\"edge IDs in this payload\"],\"passages\":[\"passage IDs in this payload\"]}}

Otherwise return only `UNRESOLVED: {{\"blocker_type\":\"...\",\"bottleneck\":\"...\",\"needed_check\":\"...\"}}`.

Question: {question}
Focus handoff: {json.dumps(handoff, ensure_ascii=False, separators=(",", ":"))}
{evidence_label}: {compact_json}
Answer:"""


class QueryEvidenceGraphPathBalanceBaseline(OnlineUnifiedEvidenceGraphBaseline):
    """Experimental QEG branch: full graph with unranked multi-path guides."""

    method_name = "qeg_path_balance"

    def __init__(self, config: RAGConfig | None = None, *, kg_builder=None, prompt_builder=None):
        balanced_config = replace(
            config or RAGConfig(),
            use_path_guidance=True,
            use_path_focused_prompt=False,
            use_adaptive_verification=True,
            require_evidence_path=False,
            use_lexical_tiebreak=False,
        )
        builder = prompt_builder or _QEGPathBalancePromptBuilder(OUEGPromptCompressionConfig(
            context_mode=balanced_config.oueg_context_mode,
            include_lexical_tiebreak=False,
        ))
        super().__init__(balanced_config, kg_builder=kg_builder, prompt_builder=builder)

class QueryEvidenceGraphSoftContractBaseline(OnlineUnifiedEvidenceGraphBaseline):
    """Answer first, then independently attach an auditable evidence path.

    This is the fair EM-oriented QEG comparison: L1/L2 retain the established
    no-path reader behaviour.  A separate ``CITE_EVIDENCE`` call sees the same
    compact graph and can only attach a path; it can never replace or suppress
    the already emitted answer.
    """

    method_name = "qeg_soft_contract"

    def __init__(self, config: RAGConfig | None = None, *, kg_builder=None, prompt_builder=None):
        soft_config = replace(
            config or RAGConfig(),
            use_path_guidance=False,
            use_path_focused_prompt=False,
            use_adaptive_verification=True,
            require_evidence_path=False,
        )
        # The standard builder is deliberate: this makes the answer phase
        # prompt-equivalent to the stronger no_path_guidance control.
        builder = prompt_builder or CompactOUEGPromptBuilder(OUEGPromptCompressionConfig(
            context_mode=soft_config.oueg_context_mode,
            include_lexical_tiebreak=soft_config.use_lexical_tiebreak,
        ))
        super().__init__(soft_config, kg_builder=kg_builder, prompt_builder=builder)

    def _valid_answer_evidence_path(self, audit: dict | None) -> bool:
        """Soft mode records only actual graph paths, never passage-only cites."""
        return bool(audit and audit.get("has_grounded_path"))

    @staticmethod
    def _cite_evidence_prompt(*, question: str, answer: str, compact_json: str, retry: bool = False) -> str:
        retry_note = (
            "Your previous citation was invalid or did not contain an edge ID. "
            "Try again using only IDs visible in this payload.\n\n"
            if retry else ""
        )
        return f"""CITE_EVIDENCE is a citation-only task. Do not answer the question again and do not change the proposed answer.

Question: {question}
Proposed answer: {answer}

Select the shortest visible evidence path that supports this exact answer. It must contain at least one edge ID (`e...`). Passage IDs (`p...`) are optional. Return exactly one line and no explanation:
EVIDENCE_PATH: {{\"edges\":[\"e...\"],\"passages\":[\"p...\"]}}

{retry_note}Compact evidence payload: {compact_json}
Citation:"""

    def run(self, example):
        result = super().run(example)
        answer = str(result.get("answer") or "").strip()
        citation = {
            "attempted": bool(answer),
            "first_response": None,
            "first_evidence_path": None,
            "retry_response": None,
            "retry_evidence_path": None,
            "final_decision": "not_attempted" if not answer else "ungrounded",
        }
        if not answer:
            result["citation_recovery"] = citation
            result["evidence_contract"] = {"mode": "soft", "required": False, "satisfied": False}
            return result

        compact_json = json.dumps(result["compact_oueg_payload"], ensure_ascii=False, separators=(",", ":"))
        allowed_refs = self._serialized_evidence_refs(compact_json)
        max_tokens = min(384, int(result.get("request_max_output_tokens") or self.config.max_output_tokens))
        first_prompt = self._cite_evidence_prompt(
            question=example.question, answer=answer, compact_json=compact_json,
        )
        first_response = llm_call(first_prompt, max_tokens=max_tokens, temperature=self.config.temperature)
        first_audit = self._evidence_path_audit(first_response, allowed_refs)
        citation["first_response"] = str(first_response or "")
        citation["first_evidence_path"] = first_audit
        final_audit = first_audit
        result["llm_calls"] = int(result.get("llm_calls") or 0) + 1
        if not self._valid_answer_evidence_path(first_audit):
            retry_prompt = self._cite_evidence_prompt(
                question=example.question, answer=answer, compact_json=compact_json, retry=True,
            )
            retry_response = llm_call(retry_prompt, max_tokens=max_tokens, temperature=self.config.temperature)
            retry_audit = self._evidence_path_audit(retry_response, allowed_refs)
            citation["retry_response"] = str(retry_response or "")
            citation["retry_evidence_path"] = retry_audit
            final_audit = retry_audit
            result["llm_calls"] += 1

        grounded = self._valid_answer_evidence_path(final_audit)
        citation["final_decision"] = "grounded" if grounded else "ungrounded_after_retry"
        result["citation_recovery"] = citation
        result["answer_evidence_path"] = final_audit
        result["answer_evidence_verified"] = grounded
        result["evidence_contract"] = {
            "mode": "soft",
            "required": False,
            "satisfied": grounded,
        }
        return result


class QueryEvidenceGraphECARBaseline(OnlineUnifiedEvidenceGraphBaseline):
    """No-path reader followed by deterministic Evidence-Constrained Answer Recovery.

    ECAR first recovers only denotations available in the retrieved
    graph/table/passage trace.  If that deterministic pass exposes a proof
    gap, it may use the one remaining bounded L2 call to repair the proof; a
    base-protocol L2 call is never followed by a third reader request.
    """

    method_name = "qeg_ecar"

    def __init__(self, config: RAGConfig | None = None, *, kg_builder=None, prompt_builder=None):
        ecar_config = replace(
            config or RAGConfig(),
            use_path_guidance=False,
            use_path_focused_prompt=False,
            use_adaptive_verification=True,
            require_evidence_path=False,
        )
        builder = prompt_builder or CompactOUEGPromptBuilder(OUEGPromptCompressionConfig(
            context_mode=ecar_config.oueg_context_mode,
            include_lexical_tiebreak=ecar_config.use_lexical_tiebreak,
        ))
        super().__init__(ecar_config, kg_builder=kg_builder, prompt_builder=builder)

    @staticmethod
    def _ecar_proof_handoff(ecar: dict) -> dict:
        """Turn a conservative ECAR rejection into an auditable L2 request."""
        gaps = [str(value) for value in ecar.get("proof_gap", []) if str(value)]
        gap_set = set(gaps)
        if gap_set & {"missing_relation_witness", "mention_only_path"}:
            blocker_type = "missing_link"
            needed_check = (
                "Verify the missing relation in the candidate's table row or linked "
                "passage, then cite every KG edge needed for that relation chain."
            )
        elif "unexecuted_ordinal" in gap_set:
            blocker_type = "candidate_collision"
            needed_check = (
                "Execute the requested rank or temporal ordering using the visible row "
                "values, then cite the record binding and ordering edge."
            )
        elif "no_candidate_path" in gap_set:
            blocker_type = "insufficient_evidence"
            needed_check = (
                "Locate a visible table-to-passage relation chain that proves the answer; "
                "do not rely on an unsupported surface mention."
            )
        else:
            blocker_type = "answer_type_uncertain"
            needed_check = (
                "Verify the answer type and its supporting relation with visible KG edge IDs."
            )

        candidates: list[str] = []
        for item in [ecar.get("selected"), *(ecar.get("top_candidates") or [])]:
            if not isinstance(item, dict):
                continue
            answer = str(item.get("answer") or "").strip()
            if answer and answer not in candidates:
                candidates.append(answer)
            if len(candidates) == 4:
                break
        return {
            "origin": "ecar_proof_gap",
            "blocker_type": blocker_type,
            "bottleneck": "ECAR could not validate the L1 answer path: " + ", ".join(gaps),
            "needed_check": needed_check,
            "candidates": candidates,
            "proof_gap": gaps,
            "ecar_selected": ecar.get("selected"),
            "non_destructive": True,
        }

    @staticmethod
    def _ecar_verification_prompt(question: str, compact_json: str, handoff: dict) -> str:
        """A bounded proof-repair pass over the same complete QEG evidence."""
        return f"""Repair the evidence proof for the answer to this question using only the compact QEG payload.

ECAR found a proof gap after the first reader answer. Treat the handoff as an
attention guide, not as evidence or an answer constraint. Verify the requested
relation, row binding, rank, or temporal order directly against visible KG edges
and passages. Do not infer facts absent from the payload.

Return exactly one of:
FINAL_ANSWER: <shortest answer span copied from evidence>
EVIDENCE_PATH: {{\"edges\":[\"e...\"],\"passages\":[\"p...\"]}}

or:
UNRESOLVED: {{\"blocker_type\":\"...\",\"bottleneck\":\"...\",\"needed_check\":\"...\"}}

A successful answer must cite at least one visible edge ID. Do not return an
answer solely because it was proposed by the first reader or ECAR.

Question: {question}
ECAR proof-repair handoff: {json.dumps(handoff, ensure_ascii=False, separators=(',', ':'))}
Compact QEG payload: {compact_json}
Answer:"""

    @classmethod
    def _parse_ecar_verification_response(cls, raw: str) -> tuple[str, dict]:
        """Parse a strict answer-plus-proof response from ECAR's repair reader.

        Unlike the base adaptive reader, proof repair cannot fall back to a
        free-form span: its protocol requires an answer on the same line as
        ``FINAL_ANSWER``.  This prevents a blank answer line followed by
        ``EVIDENCE_PATH`` from promoting the citation itself to an answer.
        """
        text = str(raw or "").strip()
        match = re.search(
            r"(?im)^FINAL[ _]+ANSWER[ \t]*:[ \t]*([^\r\n]+)", text,
        )
        if match:
            answer = cls._short_answer(match.group(1))
            if answer:
                return answer, {}

        _answer, diagnostic = cls._parse_adaptive_response(text)
        if diagnostic:
            return "", diagnostic
        return "", {
            "raw": text,
            "response_type": "invalid_proof_repair_response",
            "candidates": [],
            "bottleneck": "Missing a non-empty FINAL_ANSWER line.",
            "blocker_type": "invalid_protocol_response",
            "needed_check": "Return FINAL_ANSWER and EVIDENCE_PATH on separate valid lines.",
        }

    def run(self, example):
        started = time.perf_counter()
        result = super().run(example)
        ecar = EvidenceConstrainedAnswerRecovery.recover(
            question=example.question,
            llm_answer=str(result.get("answer") or ""),
            kg_trace=result["full_kg"],
        )
        result["ecar"] = ecar
        result["answer"] = ecar["answer"]
        selected = ecar.get("selected")
        result["answer_evidence_path"] = selected
        result["answer_evidence_verified"] = bool(ecar.get("evidence_verified"))
        proof_recovery = {
            "enabled": self.config.use_ecar_proof_recovery,
            "triggered": False,
            "skip_reason": None,
            "handoff": None,
            "response": None,
            "evidence_path": None,
            "final_decision": "not_needed",
        }
        gaps = ecar.get("proof_gap") or []
        if not self.config.use_ecar_proof_recovery:
            proof_recovery["skip_reason"] = "disabled_by_config"
            proof_recovery["final_decision"] = "l1_ecar_retained"
        elif not gaps or ecar.get("evidence_verified"):
            proof_recovery["skip_reason"] = "no_unrepaired_proof_gap"
        elif int(result.get("llm_calls") or 0) >= 2:
            # The base OUEG protocol already consumed its sole bounded L2
            # call for an L1 diagnostic. Never turn ECAR into a third call.
            proof_recovery["skip_reason"] = "l2_budget_already_consumed"
            proof_recovery["final_decision"] = "l1_ecar_retained"
        else:
            handoff = self._ecar_proof_handoff(ecar)
            compact_json = json.dumps(
                result["compact_oueg_payload"], ensure_ascii=False, separators=(",", ":"),
            )
            retry_prompt = self._ecar_verification_prompt(
                example.question, compact_json, handoff,
            )
            response = llm_call(
                retry_prompt,
                max_tokens=int(result.get("request_max_output_tokens") or self.config.max_output_tokens),
                temperature=self.config.temperature,
            )
            repaired_answer, diagnostic = self._parse_ecar_verification_response(response)
            evidence_path = self._evidence_path_audit(
                response, self._serialized_evidence_refs(compact_json),
            )
            proof_recovery.update({
                "triggered": True,
                "handoff": handoff,
                "response": str(response or ""),
                "diagnostic": diagnostic or None,
                "evidence_path": evidence_path,
                "prompt_chars": len(retry_prompt),
            })
            result["llm_calls"] = int(result.get("llm_calls") or 0) + 1
            result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            result["answer_retry_attempted"] = True
            result["retry_prompt"] = retry_prompt
            result["retry_prompt_chars"] = len(retry_prompt)
            if repaired_answer and self._valid_answer_evidence_path(evidence_path):
                l2_ecar = EvidenceConstrainedAnswerRecovery.recover(
                    question=example.question,
                    llm_answer=repaired_answer,
                    kg_trace=result["full_kg"],
                )
                # The L2 evidence path is the proof for this answer; ECAR's
                # second pass remains useful as a separate canonicalization
                # audit and must not suppress a cited L2 answer merely because
                # its heuristic proof checker stays conservative.
                ecar["l2_reader_answer"] = repaired_answer
                ecar["l2_recovery"] = l2_ecar
                result["answer"] = repaired_answer
                result["answer_evidence_path"] = evidence_path
                result["answer_evidence_verified"] = True
                proof_recovery["final_decision"] = "verified_after_ecar_proof_repair"
            else:
                proof_recovery["final_decision"] = "l1_ecar_retained_after_unverified_l2"
        result["ecar_proof_recovery"] = proof_recovery
        result["evidence_contract"] = {
            "mode": "deterministic_ecar_l2_proof_repair",
            "required": False,
            "satisfied": bool(result["answer_evidence_verified"]),
            "proof_status": ecar.get("proof_status"),
            "proof_gap": ecar.get("proof_gap", []),
            "l2_proof_repair": proof_recovery["final_decision"],
        }
        return result


class QueryEvidenceGraphECARL2EvidenceEvalBaseline(QueryEvidenceGraphECARBaseline):
    """Experimental QEG-ECAR split: L2 evaluates evidence or resolves an L1 handoff.

    The two L2 roles are deliberately mutually exclusive.  A normal L1 answer
    is retained (after deterministic ECAR) and L2 only returns an auditable
    verdict about its evidence.  If L1 instead emits ``NEED_FOCUS`` or
    ``UNRESOLVED``, the inherited OUEG adaptive branch first expands the KG and
    spends L2 on answer resolution.  This branch never asks L2 to replace a
    usable L1 answer.
    """

    method_name = "qeg_ecar_l2_evidence_eval"

    def __init__(self, config: RAGConfig | None = None, *, kg_builder=None, prompt_builder=None):
        # Disable the parent variant's L2 proof-repair call.  L2 is reserved
        # for one of the two explicit roles documented above.
        split_config = replace(config or RAGConfig(), use_ecar_proof_recovery=False)
        super().__init__(split_config, kg_builder=kg_builder, prompt_builder=prompt_builder)

    @staticmethod
    def _same_answer(left: str, right: str) -> bool:
        def normalize(value: str) -> str:
            return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
        return bool(normalize(left)) and normalize(left) == normalize(right)

    @classmethod
    def _has_viable_proof_candidate(cls, ecar: dict) -> bool:
        """Return whether ECAR exposes an answer-aligned partial graph path.

        Evidence evaluation is a bounded proof check, not a second retrieval
        pass.  It is only useful when deterministic ECAR has already located
        a candidate with visible path edges but could not discharge every
        relation or scope constraint.
        """
        selected = ecar.get("selected")
        if not isinstance(selected, dict):
            return False
        if str(ecar.get("proof_status") or "") != "partially_grounded":
            return False
        if not cls._same_answer(
            str(ecar.get("answer") or ""), str(selected.get("answer") or ""),
        ):
            return False
        edge_ids = selected.get("edge_ids")
        return isinstance(edge_ids, list) and any(str(edge_id).strip() for edge_id in edge_ids)

    @staticmethod
    def _required_evidence_claims(question: str, ecar: dict) -> list[dict]:
        """Compile claims that L2 must prove separately, including scope cues."""
        claims = [
            {
                "id": "answer_identity",
                "requirement": "Identify the proposed answer in a visible row, edge, or passage.",
            },
            {
                "id": "question_relation",
                "requirement": "Prove the relation requested by the question for the proposed answer.",
            },
        ]
        superlative = re.search(
            r"\b(first|last|earliest|latest|most|least|highest|lowest|best|worst|largest|smallest)\b",
            question, re.I,
        )
        if superlative:
            claims.append({
                "id": "scope_or_order",
                "requirement": (
                    f"Prove that the answer itself satisfies the requested `{superlative.group(1).lower()}` "
                    "constraint. Evidence about a related person, organisation, or category is insufficient."
                ),
            })
        if "missing_relation_witness" in set(ecar.get("proof_gap") or []):
            claims.append({
                "id": "relation_witness",
                "requirement": "Cite a non-mention edge that witnesses the missing relation, not merely co-occurrence.",
            })
        return claims

    @staticmethod
    def _canonical_grounded_answer(answer: str, kg_trace: dict) -> dict:
        """Shorten a generated name only to a visible canonical wiki entity.

        This is intentionally one-way: a visible title may canonicalize an L1
        expansion such as ``Nikola Dinev Nikolov`` to ``Nikola Dinev``, but the
        method never invents an alias or looks at a benchmark label.
        """
        original = str(answer or "").strip()
        normalized = re.sub(r"[^a-z0-9]+", " ", original.casefold()).strip()
        if not normalized:
            return {"answer": original, "changed": False, "source_id": None}
        candidates: list[tuple[str, str]] = []
        for node in kg_trace.get("structural_nodes", []):
            node_id = str(node.get("id") or "")
            if not node_id.startswith("/wiki/"):
                continue
            title = node_id.removeprefix("/wiki/").replace("_", " ").strip()
            title_norm = re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()
            if len(title_norm.split()) < 2 or title_norm == normalized:
                continue
            if normalized.startswith(title_norm + " "):
                candidates.append((title, node_id))
        if not candidates:
            return {"answer": original, "changed": False, "source_id": None}
        # Prefer the most-specific grounded prefix when several entity titles
        # fit the generated expansion.
        title, source_id = max(candidates, key=lambda item: len(item[0]))
        return {
            "answer": title,
            "changed": True,
            "source_id": source_id,
            "original_answer": original,
        }

    @staticmethod
    def _evidence_evaluation_prompt(*, question: str, answer: str, ecar: dict, required_claims: list[dict], compact_json: str) -> str:
        return f"""Evaluate evidence for the proposed answer using only the compact QEG payload.

This is an evidence-evaluation task, not answer generation. Do not replace,
rewrite, or propose another answer. Judge whether the visible KG edges and
passages support the exact proposed answer for the question.

Return exactly one line:
EVIDENCE_EVALUATION: {{\"verdict\":\"supported|unsupported|insufficient\",\"claim_checks\":[{{\"id\":\"...\",\"verdict\":\"supported|unsupported|insufficient\",\"edges\":[\"e...\"],\"passages\":[\"p...\"]}}],\"edges\":[\"e...\"],\"passages\":[\"p...\"],\"reason\":\"short reason\"}}

Use only IDs visible in the payload. For an overall `supported` verdict,
include every required claim exactly once and give every supported claim at
least one edge ID. If any claim lacks a direct witness, return `unsupported`
or `insufficient`; do not transfer a property from a related entity to the
answer.

Question: {question}
Proposed answer (fixed; do not alter): {answer}
Deterministic ECAR audit: {json.dumps({key: ecar.get(key) for key in ('decision', 'proof_status', 'proof_gap', 'selected')}, ensure_ascii=False, separators=(',', ':'))}
Required claim checks: {json.dumps(required_claims, ensure_ascii=False, separators=(',', ':'))}
Compact QEG payload: {compact_json}
Verdict:"""

    @staticmethod
    def _parse_evidence_evaluation(raw: str, required_claim_ids: set[str]) -> dict:
        """Read the strict evidence verdict without treating it as an answer."""
        text = str(raw or "").strip()
        match = re.search(r"EVIDENCE_EVALUATION\s*:\s*(\{.*\})", text, re.I | re.S)
        if match is None:
            return {
                "valid": False,
                "verdict": "invalid",
                "reason": "Missing EVIDENCE_EVALUATION JSON object.",
                "raw": text,
            }
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}
        verdict = str(parsed.get("verdict") or "").strip().lower()
        if verdict not in {"supported", "unsupported", "insufficient"}:
            return {
                "valid": False,
                "verdict": "invalid",
                "reason": "Verdict must be supported, unsupported, or insufficient.",
                "raw": text,
            }
        checks = parsed.get("claim_checks")
        if not isinstance(checks, list):
            checks = []
        check_ids = [str(item.get("id") or "") for item in checks if isinstance(item, dict)]
        if (
            verdict == "supported"
            and (set(check_ids) != required_claim_ids or len(check_ids) != len(required_claim_ids))
        ):
            return {
                "valid": False,
                "verdict": "invalid",
                "reason": "Supported verdict must include every required claim exactly once.",
                "raw": text,
                "claim_checks": checks,
            }
        return {
            "valid": True,
            "verdict": verdict,
            "reason": str(parsed.get("reason") or "").strip(),
            "raw": text,
            "claim_checks": checks,
        }

    def _evaluation_evidence_path_audit(self, raw: str, allowed_refs: set[str]) -> dict:
        """Audit citations embedded in an ``EVIDENCE_EVALUATION`` object."""
        match = re.search(
            r"EVIDENCE_EVALUATION\s*:\s*(\{.*\})", str(raw or ""), re.I | re.S,
        )
        if match is None:
            return self._evidence_path_audit("", allowed_refs)
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            return self._evidence_path_audit("", allowed_refs)
        if not isinstance(parsed, dict):
            return self._evidence_path_audit("", allowed_refs)
        citation = json.dumps({
            "edges": parsed.get("edges", []),
            "passages": parsed.get("passages", []),
        }, ensure_ascii=False, separators=(",", ":"))
        return self._evidence_path_audit(f"EVIDENCE_PATH: {citation}", allowed_refs)

    def run(self, example):
        result = super().run(example)
        adaptive = result.get("adaptive_verification") or {}
        canonicalization = self._canonical_grounded_answer(
            str(result.get("answer") or ""), result.get("full_kg") or {},
        )
        result["answer_canonicalization"] = canonicalization
        if canonicalization["changed"]:
            result["answer"] = canonicalization["answer"]
        answer = str(result.get("answer") or "").strip()
        evaluation = {
            "attempted": False,
            "role": "not_used",
            "skip_reason": None,
            "answer_before_l2": answer,
            "final_decision": "not_run",
        }

        # The parent OUEG branch has already used L2 for a diagnostic handoff
        # after rebuilding the KG.  It is the answer-producing L2 role; do not
        # add an evidence-evaluator call afterwards.
        if adaptive.get("triggered"):
            evaluation.update({
                "role": "answer_after_kg_augmentation",
                "skip_reason": "l1_returned_diagnostic_handoff",
                "final_decision": "answer_l2_completed",
            })
        elif not answer:
            evaluation.update({
                "skip_reason": "no_l1_answer_to_evaluate",
                "final_decision": "not_run",
            })
        elif result.get("abstained_for_ambiguity"):
            evaluation.update({
                "skip_reason": "ambiguity_abstention",
                "final_decision": "not_run",
            })
        elif bool((result.get("ecar") or {}).get("evidence_verified")):
            evaluation.update({
                "role": "deterministic_proof_attachment",
                "skip_reason": "ecar_verified_answer",
                "final_decision": "supported",
            })
        elif not self._has_viable_proof_candidate(result.get("ecar") or {}):
            proof_status = str((result.get("ecar") or {}).get("proof_status") or "unknown")
            evaluation.update({
                "skip_reason": f"ecar_{proof_status}_without_viable_candidate_path",
                "final_decision": "unproved",
            })
        else:
            required_claims = self._required_evidence_claims(
                example.question, result.get("ecar") or {},
            )
            compact_json = json.dumps(
                result["compact_oueg_payload"], ensure_ascii=False, separators=(",", ":"),
            )
            prompt = self._evidence_evaluation_prompt(
                question=example.question,
                answer=answer,
                ecar=result.get("ecar") or {},
                required_claims=required_claims,
                compact_json=compact_json,
            )
            started = time.perf_counter()
            response = llm_call(
                prompt,
                # GPT-OSS reasoning tokens share this completion budget.  A
                # 512-token ceiling frequently cuts the final one-line JSON
                # verdict mid-object even though the visible answer is short.
                max_tokens=int(result.get("request_max_output_tokens") or self.config.max_output_tokens),
                temperature=self.config.temperature,
            )
            allowed_refs = self._serialized_evidence_refs(compact_json)
            parsed = self._parse_evidence_evaluation(
                response, {claim["id"] for claim in required_claims},
            )
            evidence_path = self._evaluation_evidence_path_audit(response, allowed_refs)
            claim_audits = []
            for check in parsed.get("claim_checks") or []:
                if not isinstance(check, dict):
                    continue
                citation = json.dumps({
                    "edges": check.get("edges", []),
                    "passages": check.get("passages", []),
                }, ensure_ascii=False, separators=(",", ":"))
                audit = self._evidence_path_audit(f"EVIDENCE_PATH: {citation}", allowed_refs)
                claim_audits.append({
                    "id": str(check.get("id") or ""),
                    "verdict": str(check.get("verdict") or "").strip().lower(),
                    "evidence_path": audit,
                })
            claims_supported = (
                len(claim_audits) == len(required_claims)
                and all(
                    item["verdict"] == "supported"
                    and self._valid_answer_evidence_path(item["evidence_path"])
                    for item in claim_audits
                )
            )
            supported = (
                parsed["valid"]
                and parsed["verdict"] == "supported"
                and self._valid_answer_evidence_path(evidence_path)
                and claims_supported
            )
            evaluation.update({
                "attempted": True,
                "role": "evidence_evaluator",
                "prompt": prompt,
                "prompt_chars": len(prompt),
                "response": str(response or ""),
                "required_claims": required_claims,
                "parsed": parsed,
                "evidence_path": evidence_path,
                "claim_audits": claim_audits,
                "final_decision": "supported" if supported else "not_supported",
            })
            if supported:
                result["answer_evidence_path"] = evidence_path
                result["answer_evidence_verified"] = True
            result["llm_calls"] = int(result.get("llm_calls") or 0) + 1
            result["latency_ms"] = round(float(result.get("latency_ms") or 0) + (time.perf_counter() - started) * 1000, 2)

        # L2 never changes the denotation in this experimental branch.
        result["l2_evidence_evaluation"] = evaluation
        result["evidence_contract"] = {
            "mode": "l1_answer_l2_evidence_eval_or_augmented_l2_answer",
            "required": False,
            "satisfied": (
                evaluation["final_decision"] == "supported"
                if evaluation["attempted"]
                else bool(result.get("answer_evidence_verified"))
            ),
            "l2_role": evaluation["role"],
            "l2_decision": evaluation["final_decision"],
        }
        return result


class QueryEvidenceGraphAnswerToProofBaseline(QueryEvidenceGraphECARL2EvidenceEvalBaseline):
    """No-path reader with an answer-preserving proof attachment phase.

    This is the control needed to test whether provenance can be recovered
    without paying the accuracy cost of a path-shaped answer prompt or an
    ECAR denotation rewrite.  The L1 answer is immutable after it is emitted.
    ECAR only audits whether that *same* denotation has a graph proof.  If it
    exposes a partially grounded candidate path and ordinary OUEG L2 was not
    already used, one L2 call may evaluate the proof.  An unverified ECAR
    result is recorded as unproved rather than spending L2 to rediscover an
    absent candidate path.  That call never proposes or substitutes an answer.
    """

    method_name = "qeg_answer_to_proof"

    def __init__(self, config: RAGConfig | None = None, *, kg_builder=None, prompt_builder=None):
        proof_config = replace(
            config or RAGConfig(),
            use_path_guidance=False,
            use_path_focused_prompt=False,
            use_adaptive_verification=True,
            require_evidence_path=False,
            use_ecar_proof_recovery=False,
        )
        builder = prompt_builder or CompactOUEGPromptBuilder(OUEGPromptCompressionConfig(
            context_mode=proof_config.oueg_context_mode,
            include_lexical_tiebreak=proof_config.use_lexical_tiebreak,
        ))
        # Do not invoke QueryEvidenceGraphECARBaseline.__init__: its run
        # variant is allowed to replace L1's answer with an ECAR candidate.
        OnlineUnifiedEvidenceGraphBaseline.__init__(
            self, proof_config, kg_builder=kg_builder, prompt_builder=builder,
        )

    def run(self, example):
        # Preserve exactly the ordinary no-path OUEG reader result.  In
        # particular, neither ECAR nor the proof reader can change `answer`.
        result = OnlineUnifiedEvidenceGraphBaseline.run(self, example)
        reader_answer = str(result.get("answer") or "").strip()
        ecar = EvidenceConstrainedAnswerRecovery.recover(
            question=example.question,
            llm_answer=reader_answer,
            kg_trace=result["full_kg"],
        )
        same_denotation = self._same_answer(reader_answer, str(ecar.get("answer") or ""))
        result["answer_to_proof"] = {
            "reader_answer": reader_answer,
            "ecar_audit": ecar,
            "same_denotation": same_denotation,
        }

        evaluation = {
            "attempted": False,
            "role": "not_used",
            "skip_reason": None,
            "answer_before_l2": reader_answer,
            "final_decision": "not_run",
        }
        selected = ecar.get("selected") if isinstance(ecar.get("selected"), dict) else None
        if (
            reader_answer
            and same_denotation
            and bool(ecar.get("evidence_verified"))
            and selected is not None
        ):
            # A deterministic proof is already sufficient; no L2 bill or
            # latency is incurred.  This path always refers to the retained
            # L1 denotation.
            result["answer_evidence_path"] = selected
            result["answer_evidence_verified"] = True
            evaluation.update({
                "role": "deterministic_proof_attachment",
                "skip_reason": "ecar_verified_same_l1_answer",
                "final_decision": "supported",
            })
        elif (result.get("adaptive_verification") or {}).get("triggered"):
            # The base protocol used the one allowed reader recovery call for
            # an L1 diagnostic.  Retain its answer but make no grounding claim.
            evaluation.update({
                "role": "answer_after_kg_augmentation",
                "skip_reason": "l2_budget_used_by_l1_diagnostic",
                "final_decision": "not_run",
            })
        elif not reader_answer:
            evaluation.update({
                "skip_reason": "no_l1_answer_to_prove",
                "final_decision": "not_run",
            })
        elif result.get("abstained_for_ambiguity"):
            evaluation.update({
                "skip_reason": "ambiguity_abstention",
                "final_decision": "not_run",
            })
        elif not (
            same_denotation and self._has_viable_proof_candidate(ecar)
        ):
            proof_status = str(ecar.get("proof_status") or "unknown")
            evaluation.update({
                "skip_reason": f"ecar_{proof_status}_without_viable_same_answer_path",
                "final_decision": "unproved",
            })
        else:
            # Proof-gap-only L2. Its contract fixes the answer, so a failed
            # validator can lower no EM; it merely leaves the answer unproved.
            required_claims = self._required_evidence_claims(example.question, ecar)
            compact_json = json.dumps(
                result["compact_oueg_payload"], ensure_ascii=False, separators=(",", ":"),
            )
            prompt = self._evidence_evaluation_prompt(
                question=example.question,
                answer=reader_answer,
                ecar=ecar,
                required_claims=required_claims,
                compact_json=compact_json,
            )
            started = time.perf_counter()
            response = llm_call(
                prompt,
                max_tokens=int(result.get("request_max_output_tokens") or self.config.max_output_tokens),
                temperature=self.config.temperature,
            )
            allowed_refs = self._serialized_evidence_refs(compact_json)
            parsed = self._parse_evidence_evaluation(
                response, {claim["id"] for claim in required_claims},
            )
            evidence_path = self._evaluation_evidence_path_audit(response, allowed_refs)
            claim_audits = []
            for check in parsed.get("claim_checks") or []:
                if not isinstance(check, dict):
                    continue
                citation = json.dumps({
                    "edges": check.get("edges", []), "passages": check.get("passages", []),
                }, ensure_ascii=False, separators=(",", ":"))
                claim_audits.append({
                    "id": str(check.get("id") or ""),
                    "verdict": str(check.get("verdict") or "").strip().lower(),
                    "evidence_path": self._evidence_path_audit(
                        f"EVIDENCE_PATH: {citation}", allowed_refs,
                    ),
                })
            supported = (
                parsed["valid"]
                and parsed["verdict"] == "supported"
                and self._valid_answer_evidence_path(evidence_path)
                and len(claim_audits) == len(required_claims)
                and all(
                    item["verdict"] == "supported"
                    and self._valid_answer_evidence_path(item["evidence_path"])
                    for item in claim_audits
                )
            )
            evaluation.update({
                "attempted": True,
                "role": "proof_gap_evaluator",
                "prompt": prompt,
                "prompt_chars": len(prompt),
                "response": str(response or ""),
                "required_claims": required_claims,
                "parsed": parsed,
                "evidence_path": evidence_path,
                "claim_audits": claim_audits,
                "final_decision": "supported" if supported else "not_supported",
            })
            result["llm_calls"] = int(result.get("llm_calls") or 0) + 1
            result["latency_ms"] = round(
                float(result.get("latency_ms") or 0) + (time.perf_counter() - started) * 1000, 2,
            )
            if supported:
                result["answer_evidence_path"] = evidence_path
                result["answer_evidence_verified"] = True

        result["l2_evidence_evaluation"] = evaluation
        result["evidence_contract"] = {
            "mode": "answer_preserving_no_path_proof_attachment",
            "required": False,
            "satisfied": bool(result.get("answer_evidence_verified")),
            "l2_role": evaluation["role"],
            "l2_decision": evaluation["final_decision"],
            "proof_status": ecar.get("proof_status"),
            "proof_gap": ecar.get("proof_gap", []),
        }
        return result
