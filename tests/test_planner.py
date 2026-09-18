from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple
from src.planning import planner as planner_module
from src.planning.planner import PathPlanner


def test_generate_candidates_uses_configured_json_output_budget(monkeypatch):
    kg = OnlineKG()
    kg.add_triple(Triple("A", "relation", "B", Provenance("text", "source")))
    captured = {}

    def fake_llm_call_json(prompt, *, max_tokens):
        captured["max_tokens"] = max_tokens
        return [
            {
                "path_id": "path-1",
                "steps": [{"step": 1, "goal": "Find B", "depends_on": None}],
            }
        ]

    monkeypatch.setattr(planner_module, "llm_call_json", fake_llm_call_json)

    paths = PathPlanner(max_output_tokens=777).generate_candidates("question", kg, n=1)

    assert captured["max_tokens"] == 777
    assert paths[0].path_id == "path-1"


def test_generate_candidates_ignores_provider_extra_step_fields(monkeypatch):
    kg = OnlineKG()
    kg.add_triple(Triple("A", "relation", "B", Provenance("table", "source")))

    monkeypatch.setattr(
        planner_module,
        "llm_call_json",
        lambda prompt, **kwargs: [{
            "path_id": "extra-fields",
            "steps": [{
                "step": "1",
                "goal": "Add the selected values",
                "depends_on": None,
                "operator": "add",
                "result": "v0",
            }],
        }],
    )

    paths = PathPlanner(temperature=0).generate_candidates("sum?", kg, n=1)

    assert paths[0].path_id == "extra-fields"
    assert paths[0].steps[0].step == 1
    assert paths[0].steps[0].goal == "Add the selected values"


def test_generate_candidates_retries_one_short_path_after_malformed_json(monkeypatch):
    kg = OnlineKG()
    kg.add_triple(Triple("A", "relation", "B", Provenance("table", "source")))
    calls = []

    def fake_llm_call_json(prompt, **kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            raise ValueError("truncated JSON")
        return [{"path_id": "fallback", "steps": [
            {"step": 1, "goal": "Look up the requested cells", "depends_on": None}
        ]}]

    monkeypatch.setattr(planner_module, "llm_call_json", fake_llm_call_json)
    paths = PathPlanner().generate_candidates("question", kg, n=3)

    assert [path.path_id for path in paths] == ["fallback"]
    assert "exactly one path" in calls[1]


def test_generate_candidates_returns_empty_paths_on_provider_failure(monkeypatch):
    kg = OnlineKG()
    kg.add_triple(Triple("A", "relation", "B", Provenance("table", "source")))
    monkeypatch.setattr(
        planner_module, "llm_call_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("timeout")),
    )

    planner = PathPlanner()
    assert planner.generate_candidates("question", kg, n=1) == []
    assert planner.last_error == "RuntimeError: timeout"
