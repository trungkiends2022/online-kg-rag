import json
import sys
import threading
import time

import pytest

from src import run_baselines
from src.datasets.schema import DatasetExample


def test_one_pipeline_exception_is_recorded_instead_of_stopping(monkeypatch, tmp_path):
    examples = [
        DatasetExample("bad", "question", [], [], answer=1, metadata={"program": "add(0,1)"}),
        DatasetExample("good", "question", [], [], answer=1, metadata={"program": "add(0,1)"}),
    ]
    output = tmp_path / "results.jsonl"
    monkeypatch.setattr(run_baselines, "_examples", lambda args: examples)
    monkeypatch.setattr(run_baselines, "_make_method", lambda args: object())

    def fake_run(method, example, args):
        if example.example_id == "bad":
            raise ValueError("LLM returned invalid JSON")
        return {
            "answer": "1", "executed_value": 1,
            "candidate_diagnostics": [], "method": args.method,
        }

    monkeypatch.setattr(run_baselines, "_run_method", fake_run)
    monkeypatch.setattr(sys, "argv", [
        "run_baselines", "--dataset", "finqa", "--method", "numerical_ir",
        "--input", str(tmp_path / "unused.json"), "--output", str(output),
    ])

    run_baselines.main()

    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert len(records) == 2
    assert records[0]["run_status"] == "failed"
    assert records[0]["execution_accuracy"] == 0
    assert records[0]["error_category"] == "serialization_schema"
    assert records[1]["execution_accuracy"] == 1


def test_fail_fast_does_not_record_failed_example(monkeypatch, tmp_path):
    output = tmp_path / "results.jsonl"
    monkeypatch.setattr(run_baselines, "_examples", lambda args: [
        DatasetExample("bad", "question", [], [], answer="answer")
    ])
    monkeypatch.setattr(run_baselines, "_make_method", lambda args: object())
    monkeypatch.setattr(
        run_baselines, "_run_method",
        lambda method, example, args: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )
    monkeypatch.setattr(sys, "argv", [
        "run_baselines", "--dataset", "hybridqa", "--method", "direct_llm",
        "--input", str(tmp_path / "unused.json"), "--output", str(output),
        "--fail-fast",
    ])

    with pytest.raises(RuntimeError, match="provider unavailable"):
        run_baselines.main()

    assert output.read_text() == ""


def test_max_workers_runs_samples_concurrently_and_keeps_input_order(monkeypatch, tmp_path):
    examples = [
        DatasetExample("first", "q1", [], [], answer="a"),
        DatasetExample("second", "q2", [], [], answer="a"),
    ]
    output = tmp_path / "results.jsonl"
    monkeypatch.setattr(run_baselines, "_examples", lambda args: examples)
    monkeypatch.setattr(run_baselines, "_make_method", lambda args: object())
    started = threading.Event()

    def fake_run(method, example, args):
        started.set()
        time.sleep(0.05)
        return {"answer": "a", "executed_value": None, "method": args.method}

    monkeypatch.setattr(run_baselines, "_run_method", fake_run)
    monkeypatch.setattr(sys, "argv", [
        "run_baselines", "--dataset", "hybridqa", "--method", "direct_llm",
        "--input", str(tmp_path / "unused.json"), "--output", str(output),
        "--max-workers", "2",
    ])

    began = time.perf_counter()
    run_baselines.main()
    assert time.perf_counter() - began < 0.15
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert [record["id"] for record in records] == ["first", "second"]


def test_cli_request_concurrency_override_is_exposed_in_summary(monkeypatch, tmp_path):
    output = tmp_path / "results.jsonl"
    monkeypatch.setattr(run_baselines, "_examples", lambda args: [
        DatasetExample("one", "q", [], [], answer="a"),
    ])
    monkeypatch.setattr(run_baselines, "_make_method", lambda args: object())
    monkeypatch.setattr(
        run_baselines, "_run_method",
        lambda method, example, args: {"answer": "a", "executed_value": None, "method": args.method},
    )
    monkeypatch.setattr(sys, "argv", [
        "run_baselines", "--dataset", "hybridqa", "--input", str(tmp_path / "unused.json"),
        "--output", str(output), "--llm-max-concurrent-requests", "3",
    ])

    run_baselines.main()

    summary = json.loads((tmp_path / "results.jsonl.summary.json").read_text())
    assert summary["method"] == "online_kg_path_text"
    assert summary["config"]["llm_max_concurrent_requests"] == 3

def test_resume_requires_an_exact_run_manifest(monkeypatch, tmp_path):
    output = tmp_path / "results.jsonl"
    input_path = tmp_path / "input.json"
    input_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(run_baselines, "_examples", lambda args: [
        DatasetExample("one", "q", [], [], answer="a"),
    ])
    monkeypatch.setattr(run_baselines, "_make_method", lambda args: object())
    monkeypatch.setattr(
        run_baselines, "_run_method",
        lambda method, example, args: {"answer": "a", "executed_value": None, "method": args.method},
    )
    base_argv = [
        "run_baselines", "--dataset", "hybridqa", "--method", "direct_llm",
        "--input", str(input_path), "--output", str(output),
    ]
    monkeypatch.setattr(sys, "argv", base_argv)
    run_baselines.main()

    manifest_path = output.with_suffix(".jsonl.manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["input"]["sha256"]
    assert manifest["fingerprint"]
    assert manifest["config"]["top_k"] == 5

    monkeypatch.setattr(sys, "argv", [*base_argv, "--resume"])
    run_baselines.main()
    assert len(output.read_text(encoding="utf-8").splitlines()) == 1

    monkeypatch.setattr(sys, "argv", [*base_argv, "--resume", "--top-k", "7"])
    with pytest.raises(ValueError, match="Cannot safely resume"):
        run_baselines.main()


def test_resume_rejects_legacy_output_without_manifest(monkeypatch, tmp_path):
    output = tmp_path / "legacy.jsonl"
    output.write_text('{"id": "old"}\n', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "run_baselines", "--dataset", "hybridqa", "--input", str(tmp_path / "input.json"),
        "--output", str(output), "--resume",
    ])

    with pytest.raises(ValueError, match="missing run manifest"):
        run_baselines.main()
