"""Sinh câu trả lời tự nhiên từ kết quả execute của path tốt nhất."""

from __future__ import annotations

import json

from src.kg.online_kg import OnlineKG
from src.kg.normalization import normalize_key
from src.evaluation.evaluator import ScoredPath
from src.llm.client import llm_call


class AnswerSynthesizer:
    def __init__(self, temperature: float | None = None):
        self.temperature = temperature

    @staticmethod
    def _preferred_value(value, kg: OnlineKG):
        """Prefer a concise observed alias while preserving non-entity results."""
        if not isinstance(value, str):
            return value
        resolved = kg._resolve_entity(value)
        names = [resolved]
        names.extend(
            alias for alias, canonical in kg.entity_aliases.items()
            if kg._resolve_entity(canonical) == resolved
        )
        return min(names, key=lambda name: (len(name), name.casefold()))

    def synthesize(self, question: str, best: ScoredPath, kg: OnlineKG) -> str:
        preferred = self._preferred_value(best.exec_result.value, kg)
        # FinQA boolean denotations use yes/no rather than Python's True/False.
        # The comparison itself has already been executed and grounded.
        if isinstance(preferred, bool):
            return "yes" if preferred else "no"
        # Numeric execution is already the final denotation. Sending it through
        # a verbalizer can silently flip a sign (e.g. -2143 -> "a decline of
        # 2143") or round precision, defeating executable reasoning.
        if isinstance(preferred, (int, float)) and not isinstance(preferred, bool):
            return str(preferred)
        evidence = [
            {
                "triple": [item.head, item.relation, item.tail],
                "source_type": item.source_type,
                "source_id": item.source_id,
            }
            for item in best.exec_result.evidence[:10]
        ]
        prompt = f"""
        Question: {question}
        Kết quả thực thi (đáng tin nhất, score={best.score:.2f}): {best.exec_result.value}
        Tên hiển thị ưu tiên (alias tương đương, nếu có): {preferred}
        Lý do được chọn: {best.reasons}
        Evidence đã được sandbox xác minh: {json.dumps(evidence, ensure_ascii=False)}

        Chỉ trả về answer span ngắn nhất, không viết thành câu và không giải thích.
        Khi tên hiển thị ưu tiên là alias của cùng entity, hãy trả đúng tên đó.
        """
        if self.temperature is None:
            answer = llm_call(prompt)
        else:
            answer = llm_call(prompt, temperature=self.temperature)
        # The verbalizer may shorten an entity alias, but it must never replace
        # the executed scalar with unrelated world knowledge.
        if isinstance(preferred, (str, int, float, bool)):
            expected = normalize_key(str(preferred))
            actual = normalize_key(str(answer))
            if actual != expected:
                return str(preferred)
        return answer
