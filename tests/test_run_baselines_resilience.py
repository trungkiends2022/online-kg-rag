import json
import sys

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
