"""
Orchestrator: table+text+web -> online KG -> N path candidates -> code -> execute
             -> evaluate (execution-based) -> answer.

Chạy demo:
    python -m src.pipeline
(cần .env có ANTHROPIC_API_KEY hợp lệ, xem .env.example)
"""

from __future__ import annotations

import json

from src.retrieval.coarse_retrieval import coarse_retrieve
from src.extraction.extractor import EntityRelationExtractor
from src.kg.builder import OnlineKGBuilder
from src.planning.planner import PathPlanner
from src.execution.code_synthesizer import CodeSynthesizer
from src.execution.sandbox import SandboxExecutor
from src.evaluation.evaluator import PathEvaluator
from src.evaluation.answer_synthesizer import AnswerSynthesizer


class OnlineKGPipeline:
    def __init__(self):
        self.kg_builder = OnlineKGBuilder(EntityRelationExtractor())
        self.planner = PathPlanner()
        self.code_synth = CodeSynthesizer()
        self.executor = SandboxExecutor()
        self.evaluator = PathEvaluator()
        self.answerer = AnswerSynthesizer()

    def run(
        self,
        question: str,
        table_rows: list[dict],
        text_passages: list[dict],
        web_snippets: list[dict],
        n_paths: int = 5,
        max_replans: int = 2,
    ) -> dict:
        retrieved = coarse_retrieve(question, table_rows, text_passages, web_snippets)
        kg = self.kg_builder.build(retrieved)

        for attempt in range(max_replans + 1):
            if kg.is_empty():
                return {"answer": None, "error": "Online KG rỗng — không đủ dữ liệu retrieve."}

            paths = self.planner.generate_candidates(question, kg, n=n_paths)

            candidates = []
            for path in paths:
                code = self.code_synth.synthesize(path, question)
                result = self.executor.run(code, kg)
                candidates.append((path, code, result))

            scored = self.evaluator.evaluate_all(candidates)
            best = scored[0] if scored else None

            if best and best.score > float("-inf"):
                answer = self.answerer.synthesize(question, best, kg)
                return {
                    "answer": answer,
                    "best_path_id": best.path.path_id,
                    "best_score": best.score,
                    "best_code": best.code,
                    "kg_summary": kg.summary(),
                    "replans_used": attempt,
                }
            # không path nào khả dụng -> replan (vòng lặp tiếp theo sinh path mới)

        return {"answer": None, "error": "Không tìm được path khả thi sau khi replan."}


if __name__ == "__main__":
    pipeline = OnlineKGPipeline()

    question = "Công ty nào có doanh thu quý gần nhất cao nhất trong nhóm công nghệ?"
    table_rows = [{
        "table_name": "revenue_q_latest",
        "rows": [
            {"company": "Alpha Tech", "sector": "Technology", "revenue_musd": 120},
            {"company": "Beta Foods", "sector": "Consumer", "revenue_musd": 80},
        ],
    }]
    text_passages = [{
        "id": "p1",
        "text": "Alpha Tech vừa công bố báo cáo quý với doanh thu tăng trưởng mạnh so với cùng kỳ.",
    }]
    web_snippets = [{
        "url": "https://example.com/news/alpha-tech-q-report",
        "text": "Alpha Tech is classified under the Technology sector per latest filings.",
    }]

    out = pipeline.run(question, table_rows, text_passages, web_snippets)
    print(json.dumps(out, indent=2, default=str, ensure_ascii=False))
