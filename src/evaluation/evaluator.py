"""Chấm điểm path DỰA TRÊN kết quả execute thật, không dựa trên LLM tự đọc path.

Thứ tự ưu tiên:
  1. Executability (lọc cứng: code lỗi hoặc kết quả rỗng -> loại)
  2. Self-consistency (đồng thuận giữa nhiều path độc lập -- tín hiệu chính)
  3. Length penalty (path ngắn hơn được ưu tiên nhẹ, tie-breaker)

Có thể mở rộng thêm LLM-plausibility check ở tầng 3 nếu cần (chấm SAU khi đã có
kết quả thực thi, không phải chấm trước khi execute).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

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
    def evaluate_all(
        self, candidates: list[tuple[ReasoningPath, str, ExecResult]]
    ) -> list[ScoredPath]:
        scored: list[ScoredPath] = []

        value_counts = Counter(
            self._normalize(r.value) for _, _, r in candidates if r.success and not r.is_empty
        )
        total_valid = sum(value_counts.values()) or 1

        for path, code, result in candidates:
            if not result.success:
                scored.append(ScoredPath(path, code, result, float("-inf"),
                                          [f"execution error: {result.error}"]))
                continue
            if result.is_empty:
                scored.append(ScoredPath(path, code, result, float("-inf"),
                                          ["empty result (dead-end)"]))
                continue

            reasons = []
            agreement = value_counts[self._normalize(result.value)] / total_valid
            score = agreement * 10
            reasons.append(f"self-consistency agreement={agreement:.2f}")

            length_penalty = 0.5 * len(path.steps)
            score -= length_penalty
            reasons.append(f"length_penalty=-{length_penalty:.1f}")

            scored.append(ScoredPath(path, code, result, score, reasons))

        return sorted(scored, key=lambda s: s.score, reverse=True)

    @staticmethod
    def _normalize(value: Any) -> str:
        if isinstance(value, (list, set)):
            return json.dumps(sorted(map(str, value)))
        return json.dumps(value, default=str)
