"""
Orchestrator: table+text+web -> online KG -> N path candidates -> code -> execute
             -> evaluate (execution-based) -> answer.

Chạy demo:
    python -m src.pipeline
(cần .env có ANTHROPIC_API_KEY hợp lệ, xem .env.example)
"""

from __future__ import annotations

import json

from src.retrieval.coarse_retrieval import two_stage_retrieve
from src.extraction.extractor import EntityRelationExtractor
from src.kg.builder import OnlineKGBuilder
from src.planning.planner import PathPlanner
from src.planning.symbolic_search import SymbolicPathSearcher
from src.planning.operation_intent import infer_operation_intent
from src.execution.code_synthesizer import CodeSynthesizer
from src.execution.sandbox import ExecResult, SandboxExecutor
from src.execution.numerical_ir import (
    NumericalIRExecutor,
    NumericalIRSynthesizer,
)
from src.execution.finqa_templates import deterministic_numerical_candidates
from src.evaluation.evaluator import PathEvaluator
from src.evaluation.answer_synthesizer import AnswerSynthesizer


class OnlineKGPipeline:
    def __init__(
        self,
        temperature: float | None = None,
        execution_mode: str = "python",
        finqa_canonical_ratio: bool = False,
        max_output_tokens: int = 4096,
    ):
        if execution_mode not in {"python", "numerical_ir"}:
            raise ValueError(f"unsupported execution mode: {execution_mode}")
        self.execution_mode = execution_mode
        self.finqa_canonical_ratio = finqa_canonical_ratio
        self.max_output_tokens = max_output_tokens
        self.kg_builder = OnlineKGBuilder(
            EntityRelationExtractor(
                temperature=temperature, max_output_tokens=max_output_tokens
            )
        )
        self.planner = PathPlanner(
            temperature=temperature, max_output_tokens=max_output_tokens
        )
        self.symbolic_search = SymbolicPathSearcher()
        self.code_synth = CodeSynthesizer(temperature=temperature)
        self.executor = SandboxExecutor()
        self.ir_synth = NumericalIRSynthesizer(
            temperature=temperature, max_output_tokens=max_output_tokens
        )
        self.ir_executor = NumericalIRExecutor()
        self.evaluator = PathEvaluator()
        self.answerer = AnswerSynthesizer(temperature=temperature)

    @staticmethod
    def _evidence_record(item) -> dict:
        return {
            "head": item.head,
            "relation": item.relation,
            "tail": item.tail,
            "source_type": item.source_type,
            "source_id": item.source_id,
            "row_index": item.row_index,
            "column_name": item.column_name,
            "header_path": item.header_path,
            "text_context": item.text_context,
        }

    def run(
        self,
        question: str,
        table_rows: list[dict],
        text_passages: list[dict],
        web_snippets: list[dict],
        n_paths: int = 5,
        max_replans: int = 2,
        retrieval_top_k: int = 10,
        retrieval_second_stage_k: int = 3,
    ) -> dict:
        retrieved = two_stage_retrieve(
            question, table_rows, text_passages, web_snippets,
            top_k=retrieval_top_k, second_stage_k=retrieval_second_stage_k,
        )
        kg = self.kg_builder.build(retrieved)
        constraint_context = retrieved.get("retrieval_trace", {})
        operation_intent = infer_operation_intent(question, kg)
        last_diagnostics = []

        for attempt in range(max_replans + 1):
            if kg.is_empty():
                return {"answer": None, "error": "Online KG rỗng — không đủ dữ liệu retrieve."}

            template_candidates = (
                deterministic_numerical_candidates(question, kg)
                if self.execution_mode == "numerical_ir" else []
            )
            try:
                paths = (
                    self.planner.generate_candidates(
                        question, kg, n=n_paths, constraint_context=constraint_context,
                    )
                    if n_paths > 0 else []
                )
            except Exception as error:
                # Planning is optional: templates and symbolic search can still
                # solve a case.  Keep a diagnostic instead of failing the whole
                # benchmark item when a provider or a custom planner crashes.
                self.planner.last_error = f"{type(error).__name__}: {error}"
                paths = []

            candidates = []
            ir_validation: dict[str, tuple[bool, bool]] = {}
            # High-confidence table templates use the exact same typed IR and
            # executor as model programs. They are included as candidates rather
            # than replacing planning, so the evidence-aware evaluator can still
            # reject them when their grounded trace is weaker.
            if self.execution_mode == "numerical_ir":
                for template_path, template_program in template_candidates:
                    code = json.dumps(template_program.to_dict(), ensure_ascii=False)
                    result = self.ir_executor.run(template_program, kg)
                    ir_validation[template_path.path_id] = (True, True)
                    candidates.append((template_path, code, result))
            for path in paths:
                try:
                    if self.execution_mode == "numerical_ir":
                        program = self.ir_synth.synthesize(
                            path,
                            question,
                            kg,
                            finqa_canonical_ratio=self.finqa_canonical_ratio,
                        )
                        code = json.dumps(program.to_dict(), ensure_ascii=False)
                        result = self.ir_executor.run(program, kg)
                        ir_validation[path.path_id] = (True, True)
                    else:
                        code = self.code_synth.synthesize(
                            path, question, kg, constraint_context=constraint_context,
                        )
                        result = self.executor.run(code, kg)
                except Exception as exc:
                    # A malformed candidate is an expected model failure.  Keep it
                    # in the trace and let the evaluator reject just this path,
                    # instead of aborting the whole example and losing good paths.
                    code = ""
                    result = ExecResult(
                        success=False,
                        error=f"code synthesis failed: {exc}",
                        is_empty=True,
                    )
                    if self.execution_mode == "numerical_ir":
                        ir_validation[path.path_id] = (
                            bool(getattr(exc, "parse_valid", False)),
                            bool(getattr(exc, "schema_valid", False)),
                        )
                candidates.append((path, code, result))

            constraint_policy = constraint_context.get("constraint_policy", {})
            scored = self.evaluator.evaluate_all(
                candidates, constraint_policy, question=question
            )
            # Deterministic entity-centric paths complement, rather than only
            # rescue, LLM-generated programs. This makes table -> bridge entity
            # -> linked passage patterns available even when a planner returns
            # a plausible but incomplete path.
            if self.execution_mode == "python":
                symbolic_candidates = self.symbolic_search.search(question, kg)
                if symbolic_candidates:
                    candidates.extend(symbolic_candidates)
                    scored = self.evaluator.evaluate_all(
                        candidates, constraint_policy, question=question
                    )
            # Symbolic graph search returns an already executed path rather than
            # a numerical program. Disable it for the IR ablation so the method
            # cannot silently fall back to a different execution formalism.
            if (
                self.execution_mode == "python"
                and not any(item.score > float("-inf") for item in scored)
            ):
                symbolic_candidates = self.symbolic_search.search(question, kg)
                if symbolic_candidates:
                    candidates.extend(symbolic_candidates)
                    scored = self.evaluator.evaluate_all(
                        candidates, constraint_policy, question=question
                    )
            last_diagnostics = [
                {
                    "path_id": item.path.path_id,
                    "score": item.score,
                    "success": item.exec_result.success,
                    "is_empty": item.exec_result.is_empty,
                    "value": item.exec_result.value,
                    "error": item.exec_result.error,
                    "ir_parse_valid": (
                        ir_validation.get(item.path.path_id, (False, False))[0]
                        if self.execution_mode == "numerical_ir" else None
                    ),
                    "schema_valid": (
                        ir_validation.get(item.path.path_id, (False, False))[1]
                        if self.execution_mode == "numerical_ir" else None
                    ),
                    "step_values": item.exec_result.step_values,
                    "operator_trace": list(item.exec_result.operator_trace),
                    "reasons": item.reasons,
                    "steps": [step.goal for step in item.path.steps],
                    "evidence": [
                        self._evidence_record(evidence)
                        for evidence in item.exec_result.evidence
                    ],
                }
                for item in scored
            ]
            best = scored[0] if scored else None

            if best and best.score > float("-inf"):
                answer = self.answerer.synthesize(question, best, kg)
                source_types = {item.source_type for item in best.exec_result.evidence}
                path_metrics = {
                    "path_completed": True,
                    "path_length": len(best.path.steps),
                    "path_evidence_count": len(best.exec_result.evidence),
                    "path_source_types": sorted(source_types),
                    "cross_modal_path": "table" in source_types and "text" in source_types,
                    "path_precision": (
                        len(self.evaluator._direct_evidence(best.exec_result.value, best.exec_result.evidence))
                        / max(best.exec_result.accessed_edges, 1)
                    ),
                }
                return {
                    "answer": answer,
                    "executed_value": best.exec_result.value,
                    "best_path_id": best.path.path_id,
                    "best_score": best.score,
                    "best_code": best.code,
                    "best_program": (
                        json.loads(best.code)
                        if self.execution_mode == "numerical_ir"
                        else None
                    ),
                    "best_evidence": [
                        self._evidence_record(evidence)
                        for evidence in best.exec_result.evidence
                    ],
                    "best_step_values": best.exec_result.step_values,
                    "best_operator_trace": list(best.exec_result.operator_trace),
                    "kg_summary": kg.summary(),
                    "full_kg": kg.to_trace(),
                    "operation_intent": operation_intent,
                    "candidate_diagnostics": last_diagnostics,
                    "planner_error": self.planner.last_error,
                    "extraction_errors": kg.extraction_errors,
                    "replans_used": attempt,
                    "execution_mode": self.execution_mode,
                    "retrieval_trace": retrieved.get("retrieval_trace", {}),
                    "entity_anchor": retrieved.get("retrieval_trace", {}).get("entity_anchor", {}),
                    "path_metrics": path_metrics,
                    "answer_trace": {
                        "answer": answer,
                        "executed_value": best.exec_result.value,
                        "supporting_sources": sorted({item.source_id for item in best.exec_result.evidence}),
                        "confidence": round(min(max(best.score / 10.0, 0.0), 1.0), 4),
                    },
                }
            # không path nào khả dụng -> replan (vòng lặp tiếp theo sinh path mới)

        return {
            "answer": None,
            "error": "Không tìm được path khả thi sau khi replan.",
            "kg_summary": kg.summary(),
            "full_kg": kg.to_trace(),
            "operation_intent": operation_intent,
            "candidate_diagnostics": last_diagnostics,
            "planner_error": self.planner.last_error,
            "extraction_errors": kg.extraction_errors,
            "replans_used": max_replans,
            "retrieval_trace": retrieved.get("retrieval_trace", {}),
            "entity_anchor": retrieved.get("retrieval_trace", {}).get("entity_anchor", {}),
            "path_metrics": {"path_completed": False, "path_length": 0, "path_evidence_count": 0,
                             "path_source_types": [], "cross_modal_path": False, "path_precision": 0.0},
            "answer_trace": {"answer": None, "executed_value": None, "supporting_sources": [], "confidence": 0.0},
        }


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
