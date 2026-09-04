"""Sinh câu trả lời tự nhiên từ kết quả execute của path tốt nhất."""

from __future__ import annotations

from src.kg.online_kg import OnlineKG
from src.evaluation.evaluator import ScoredPath
from src.llm.client import llm_call


class AnswerSynthesizer:
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
        prompt = f"""
        Question: {question}
        Kết quả thực thi (đáng tin nhất, score={best.score:.2f}): {best.exec_result.value}
        Tên hiển thị ưu tiên (alias tương đương, nếu có): {preferred}
        Lý do được chọn: {best.reasons}

        Viết câu trả lời tự nhiên, ngắn gọn, dựa đúng vào kết quả trên. Khi tên
        hiển thị ưu tiên là alias của cùng entity, hãy dùng tên đó trong câu trả lời.
        """
        return llm_call(prompt)
