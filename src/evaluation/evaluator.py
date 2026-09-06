"""Grounded-consistency scoring based on executed paths and verified KG evidence."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from src.kg.normalization import normalize_key
from src.kg.schema import EvidenceRef
from src.planning.planner import ReasoningPath
from src.execution.sandbox import ExecResult


@dataclass
class ScoredPath:
    path: ReasoningPath
    code: str
    exec_result: ExecResult
    score: float
    reasons: list[str] = field(default_factory=list)


class PathEvaluator:
    """Prefer outputs supported by diverse, independent executed evidence."""

    def evaluate_all(
        self, candidates: list[tuple[ReasoningPath, str, ExecResult]]
    ) -> list[ScoredPath]:
        valid = [item for item in candidates if item[2].success and not item[2].is_empty]
        value_counts = Counter(self._normalize(result.value) for _, _, result in valid)
        total_valid = sum(value_counts.values()) or 1

        evidence_by_output: dict[str, set[EvidenceRef]] = defaultdict(set)
        directly_grounded: dict[int, set[EvidenceRef]] = {}
        grounding_mode: dict[int, str] = {}
        for _, _, result in valid:
            direct = self._direct_evidence(result.value, result.evidence)
            directly_grounded[id(result)] = direct
            mode = "direct" if direct else (
                "derived_numeric" if result.evidence and self._is_numeric_result(result.value) else "none"
            )
            grounding_mode[id(result)] = mode
            if mode != "none":
                # Direct evidence grounds the output. All edges accessed by that
                # path form its verified reasoning chain and add source diversity.
                evidence_by_output[self._normalize(result.value)].update(result.evidence)

        scored = []
        for path, code, result in candidates:
            if not result.success:
                scored.append(ScoredPath(path, code, result, float("-inf"),
                                         [f"execution error: {result.error}"]))
                continue
            if result.is_empty:
                scored.append(ScoredPath(path, code, result, float("-inf"),
                                         ["empty result (dead-end)"]))
                continue

            direct = directly_grounded.get(id(result), set())
            mode = grounding_mode.get(id(result), "none")
            if not result.evidence or mode == "none":
                scored.append(ScoredPath(path, code, result, float("-inf"),
                                         ["ungrounded output (no supporting KG edge)"]))
                continue

            output_key = self._normalize(result.value)
            group_evidence = evidence_by_output[output_key]
            sources = {(e.source_type, e.source_id) for e in group_evidence}
            source_types = {e.source_type for e in group_evidence}
            triples = {(e.head, e.relation, e.tail) for e in group_evidence}

            source_support = min(len(sources) / 3.0, 1.0)
            triple_support = min(len(triples) / 4.0, 1.0)
            agreement = value_counts[output_key] / total_valid
            precision = (
                len(direct) / max(result.accessed_edges, len(result.evidence), 1)
                if mode == "direct" else 0.5
            )

            has_table = "table" in source_types
            has_text = "text" in source_types
            has_web = "web" in source_types
            provenance_bonus = (
                2.0 * has_table
                + 1.0 * has_text
                + 0.25 * has_web
                + 1.5 * (has_table and has_text)
            )

            length_penalty = 0.5 * len(path.steps)
            score = (
                4.0 * source_support
                + provenance_bonus
                + 1.5 * triple_support
                + agreement
                + precision
                - length_penalty
            )
            reasons = [
                f"grounded_sources={len(sources)}",
                f"unique_triples={len(triples)}",
                f"provenance_types={','.join(sorted(source_types))}",
                f"grounding_mode={mode}",
                f"table_support=+{2.0 if has_table else 0.0:.2f}",
                f"text_support=+{1.0 if has_text else 0.0:.2f}",
                f"web_support=+{0.25 if has_web else 0.0:.2f}",
                f"cross_modality_bonus=+{1.5 if has_table and has_text else 0.0:.2f}",
                f"path_agreement={agreement:.2f}",
                f"evidence_precision={precision:.2f}",
                f"length_penalty=-{length_penalty:.1f}",
            ]
            scored.append(ScoredPath(path, code, result, score, reasons))

        return sorted(scored, key=lambda item: item.score, reverse=True)

    @staticmethod
    def _normalize(value: Any) -> str:
        if isinstance(value, (list, set, tuple)):
            return json.dumps(sorted(map(str, value)), ensure_ascii=False)
        return json.dumps(value, default=str, ensure_ascii=False)

    @classmethod
    def _value_terms(cls, value: Any) -> set[str]:
        if isinstance(value, (list, set, tuple)):
            return {term for item in value for term in cls._value_terms(item)}
        if isinstance(value, dict):
            return {term for item in value.values() for term in cls._value_terms(item)}
        term = normalize_key(str(value))
        return {term} if term else set()

    @classmethod
    def _direct_evidence(
        cls, value: Any, evidence: tuple[EvidenceRef, ...]
    ) -> set[EvidenceRef]:
        terms = cls._value_terms(value)
        direct = set()
        for item in evidence:
            endpoints = (normalize_key(item.head), normalize_key(item.tail))
            for term in terms:
                if any(
                    term == endpoint or term in endpoint.split() or endpoint in term
                    for endpoint in endpoints
                ):
                    direct.add(item)
                    break
        return direct

    @staticmethod
    def _is_numeric_result(value: Any) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            try:
                float(value.replace(",", "").strip().rstrip("%"))
                return True
            except ValueError:
                return False
        return False
