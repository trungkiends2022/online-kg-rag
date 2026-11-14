from src.execution.sandbox import ExecResult
from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple
from src.pipeline import OnlineKGPipeline
from src.planning.planner import PathStep, ReasoningPath


def test_pipeline_stops_code_and_sandbox_after_first_grounded_path(monkeypatch):
    kg = OnlineKG()
    kg.add_triple(Triple("Alpha", "answer", "Victory", Provenance("table", "t1")))
    first = ReasoningPath("first", [PathStep(1, "Read Alpha answer")])
    second = ReasoningPath("second", [PathStep(1, "This must not execute")])
    pipeline = OnlineKGPipeline()
    calls = []

    monkeypatch.setattr(pipeline.kg_builder, "build", lambda _: kg)
    monkeypatch.setattr(pipeline.planner, "generate_candidates", lambda *args, **kwargs: [first, second])
    monkeypatch.setattr(pipeline.code_synth, "synthesize", lambda path, *args, **kwargs: calls.append(path.path_id) or "code")
    monkeypatch.setattr(
        pipeline.executor, "run",
        lambda code, graph: ExecResult(
            success=True,
            value="Victory",
            evidence=tuple(graph.get_evidence("Alpha", "Victory", "answer")),
            accessed_edges=1,
        ),
    )
    monkeypatch.setattr(pipeline.answerer, "synthesize", lambda question, best, graph: str(best.exec_result.value))
    monkeypatch.setattr(
        pipeline.symbolic_search, "search",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("symbolic fallback must not run")),
    )

    result = pipeline.run("What is Alpha's answer?", [], [], [], n_paths=2, max_replans=2)

    assert calls == ["first"]
    assert result["answer"] == "Victory"
    assert result["replans_used"] == 0
    assert result["early_exit_path_id"] == "first"
