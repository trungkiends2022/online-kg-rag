from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple
from src.planning import planner as planner_module
from src.planning.planner import PathPlanner


def test_generate_candidates_uses_large_json_output_budget(monkeypatch):
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

    paths = PathPlanner().generate_candidates("question", kg, n=1)

    assert captured["max_tokens"] == 4096
    assert paths[0].path_id == "path-1"
