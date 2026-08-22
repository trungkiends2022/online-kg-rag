"""Sinh câu trả lời tự nhiên từ kết quả execute của path tốt nhất."""

from __future__ import annotations

from src.kg.online_kg import OnlineKG
from src.evaluation.evaluator import ScoredPath
from src.llm.client import llm_call


class AnswerSynthesizer:
    def synthesize(self, question: str, best: ScoredPath, kg: OnlineKG) -> str:
        prompt = f"""
        Question: {question}
        Kết quả thực thi (đáng tin nhất, score={best.score:.2f}): {best.exec_result.value}
        Lý do được chọn: {best.reasons}

        Viết câu trả lời tự nhiên, ngắn gọn, dựa đúng vào kết quả trên.
        """
        return llm_call(prompt)
