"""Ungrounded path-voting evaluator used as an Online-KG ablation baseline."""

from __future__ import annotations

from collections import Counter

from src.evaluation.evaluator import PathEvaluator, ScoredPath


class PathConsistencyEvaluator(PathEvaluator):
    """Rank executable, non-empty paths only by output agreement."""

    def evaluate_all(self, candidates, constraint_policy=None, question=None):
        # Keep the ablation deliberately limited to voting, while accepting the
        # full evaluator interface used by OnlineKGPipeline.
        del constraint_policy, question
        valid = [item for item in candidates if item[2].success and not item[2].is_empty]
        counts = Counter(self._normalize(result.value) for _, _, result in valid)
        scored = []
        for path, code, result in candidates:
            if not result.success:
                scored.append(ScoredPath(
                    path, code, result, float("-inf"),
                    [f"execution error: {result.error}"],
                ))
            elif result.is_empty:
                scored.append(ScoredPath(
                    path, code, result, float("-inf"), ["empty result (dead-end)"],
                ))
            else:
                votes = counts[self._normalize(result.value)]
                scored.append(ScoredPath(
                    path, code, result, float(votes), [f"path_votes={votes}"],
                ))
        return sorted(scored, key=lambda item: item.score, reverse=True)
