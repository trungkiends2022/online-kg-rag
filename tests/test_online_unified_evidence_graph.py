import pytest

from src.baselines.online_unified_evidence_graph import (
    OnlineUnifiedEvidenceGraphBaseline,
    _VerbatimOUEGPromptBuilder,
)
from src.baselines.rag_variants import RAGConfig
from src.datasets.schema import DatasetExample
from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple


def _kg_with_rows():
    kg = OnlineKG()
    rows = [
        {"Club": "Club Late", "Formed": "1990", "City / Town": "Gaborone"},
        {"Club": "Club Early", "Formed": "1960", "City / Town": "Gaborone"},
        {"Club": "Club Other", "Formed": "1970", "City / Town": "Francistown"},
    ]
    links = [
        {"row_index": index, "column_name": "City / Town", "cell_value": row["City / Town"],
         "url": "/wiki/Gaborone" if row["City / Town"] == "Gaborone" else "/wiki/Francistown"}
        for index, row in enumerate(rows)
    ]
    kg.register_table_structure("League", rows, cell_links=links)
    kg.register_passage("/wiki/Gaborone", "Gaborone is situated between Kgale and Oodi Hills.")
    kg.register_passage("/wiki/Francistown", "Francistown is a city in Botswana.")
    kg.add_triple(Triple(
        "Gaborone", "situated_between_landmark", "Oodi Hills",
        Provenance("text", "/wiki/Gaborone", "situated between", source_group="rule_text"),
    ))
    return kg


def _kg_with_rate_collision(*, uniquely_river_named: bool) -> OnlineKG:
    """Two structurally tied rows; text either resolves or preserves the tie."""
    kg = OnlineKG()
    rows = [
        {"Jurisdiction": "Alpha", "Rate": "21%"},
        {"Jurisdiction": "Beta", "Rate": "21%"},
    ]
    kg.register_table_structure("Rates", rows, cell_links=[
        {"row_index": 0, "column_name": "Jurisdiction", "cell_value": "Alpha", "url": "/wiki/Alpha"},
        {"row_index": 1, "column_name": "Jurisdiction", "cell_value": "Beta", "url": "/wiki/Beta"},
    ])
    alpha_text = (
        "Alpha is not named after a river."
        if uniquely_river_named else "Alpha is named after the Alpha River."
    )
    beta_text = "Beta is named after the Beta River."
    kg.register_passage("/wiki/Alpha", alpha_text)
    kg.register_passage("/wiki/Beta", beta_text)
    kg.add_triple(Triple(
        "Alpha", "origin",
        "not named after a river" if uniquely_river_named else "Alpha River",
        Provenance("text", "/wiki/Alpha", alpha_text, source_group="rule_text"),
    ))
    kg.add_triple(Triple(
        "Beta", "named_after", "Beta River",
        Provenance("text", "/wiki/Beta", beta_text, source_group="rule_text"),
    ))
    return kg


def test_oueg_suggested_paths_keep_every_structural_row_without_top_k():
    paths = OnlineUnifiedEvidenceGraphBaseline._candidate_rows(
        "Which club is in the city situated between Kgale and Oodi Hills?",
        _kg_with_rows().path_edge_records(),
    )

    assert [path["path_id"] for path in paths] == ["row_0", "row_1", "row_2"]
    assert all(path["role"] == "candidate" for path in paths)
    assert all("rank" not in path for path in paths)
    assert all(path["steps"][0].endswith("has_record--> table:League:row:" + path["path_id"].removeprefix("row_"))
               for path in paths)
    row_zero_steps = next(path["steps"] for path in paths if path["path_id"] == "row_0")
    assert any("Gaborone --situated_between_landmark--> Oodi Hills" in step
               for step in row_zero_steps)
    assert sum("Gaborone --linked_passage-->" in step for step in row_zero_steps) == 1


def test_oueg_ordering_hint_sorts_complete_candidate_set_by_temporal_column():
    candidates = OnlineUnifiedEvidenceGraphBaseline._candidate_rows(
        "Which club was first formed?", _kg_with_rows().path_edge_records(),
    )

    hint, ordered = OnlineUnifiedEvidenceGraphBaseline._ordering_hint(
        "Which club was first formed?", candidates,
    )

    assert hint["detected_signal"] == "ordinal_rank"
    assert hint["ordinal_rank"] == 1
    assert hint["sort_by_column"] == "Formed"
    assert [path["path_id"] for path in ordered] == ["row_1", "row_2", "row_0"]
    assert {path["path_id"] for path in ordered} == {"row_0", "row_1", "row_2"}


def test_oueg_ordering_hint_prioritizes_ordinal_over_counting_and_reverses_before():
    candidates = OnlineUnifiedEvidenceGraphBaseline._candidate_rows(
        "How many goals did the 10th-ranked club score?", _kg_with_rows().path_edge_records(),
    )
    hint, _ = OnlineUnifiedEvidenceGraphBaseline._ordering_hint(
        "How many goals did the 10th-ranked club score?", candidates,
    )
    assert hint["detected_signal"] == "ordinal_rank"
    assert hint["ordinal_rank"] == 10

    hint, ordered = OnlineUnifiedEvidenceGraphBaseline._ordering_hint(
        "Which club was formed before 1980?", candidates,
    )
    assert hint["direction"] == "descending"
    assert [path["path_id"] for path in ordered] == ["row_0", "row_2", "row_1"]


def test_oueg_ordering_hint_descends_for_recent_wording():
    candidates = OnlineUnifiedEvidenceGraphBaseline._candidate_rows(
        "Which club was most recently formed?", _kg_with_rows().path_edge_records(),
    )
    for question in (
        "Which club was most recent?",
        "Which club formed recently?",
        "Which is the newest club?",
    ):
        hint, ordered = OnlineUnifiedEvidenceGraphBaseline._ordering_hint(question, candidates)
        assert hint["direction"] == "descending"
        assert [path["path_id"] for path in ordered] == ["row_0", "row_2", "row_1"]


def test_oueg_prompt_keeps_full_subgraph_while_paths_are_only_guides(monkeypatch):
    kg = _kg_with_rows()

    class Builder:
        def build(self, retrieved):
            return kg

    example = DatasetExample(
        example_id="oueg", question="Which club is in Gaborone?",
        table_rows=[], text_passages=[], answer="Club Early",
    )
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.two_stage_retrieve",
        lambda *args, **kwargs: {"retrieval_trace": {}},
    )
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "fake"})(),
    )
    prompts = []
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.llm_call",
        lambda prompt, **kwargs: prompts.append(prompt) or "Club Early",
    )

    result = OnlineUnifiedEvidenceGraphBaseline(
        RAGConfig(max_output_tokens=32), kg_builder=Builder(),
    ).run(example)

    payload = result["oueg_payload"]
    assert result["answer"] == "Club Early"
    row_paths = [path for path in payload["suggested_paths"] if path["path_kind"] == "row_bundle"]
    assert len(row_paths) == 3
    assert all("score_components" in path and "presentation_score" in path for path in row_paths)
    assert any(
        edge["head"] == "Gaborone"
        and edge["relation"] == "situated_between_landmark"
        for edge in payload["subgraph"]["kg_edges"]
    )
    assert "/wiki/Gaborone" in {
        context["source_id"] for context in payload["subgraph"]["text_contexts"]
    }
    row_node = next(
        node for node in payload["subgraph"]["nodes"]
        if node["id"] == "table:League:row:0"
    )
    assert any(
        annotation["path_id"] == "row_0"
        and annotation["step_index"] == 1
        and annotation["row_order_index"] == 0
        for annotation in row_node["path_annotations"]
    )
    assert any(
        edge["head"] == "table:League"
        and edge["relation"] == "row_contains"
        and edge["tail"] == "table:League:row:0"
        for edge in payload["subgraph"]["kg_edges"]
    )
    assert any(
        edge["head"] == "table:League:row:0:cell:City / Town"
        and edge["relation"] == "column_of"
        and edge["tail"] == "table:League:column:City / Town"
        for edge in payload["subgraph"]["kg_edges"]
    )
    assert "`rows` retains table rows selected by grounded paths" in prompts[0]
    assert result["prompt_compression"]["all_edges_represented"] is True
    assert result["answer_time_evidence"]["enabled"] is True
    assert result["answer_time_evidence"]["selected_record_count"] < result["answer_time_evidence"]["full_record_count"]
    assert "nodes" not in result["compact_oueg_payload"]


def test_oueg_answer_time_evidence_keeps_only_top_grounded_paths():
    baseline = OnlineUnifiedEvidenceGraphBaseline(RAGConfig(prompt_path_budget=1))
    records = [
        {"edge_id": "e0", "tail": "passage:/wiki/Alpha", "contexts": []},
        {"edge_id": "e1", "tail": "passage:/wiki/Beta", "contexts": []},
    ]
    selected_records, selected_contexts, selected_paths, audit = baseline._answer_time_evidence(
        records,
        {
            "/wiki/Alpha": {"source_id": "/wiki/Alpha", "text": "alpha"},
            "/wiki/Beta": {"source_id": "/wiki/Beta", "text": "beta"},
        },
        [
            {"path_id": "lower", "path_kind": "seed_expansion", "score": 1.0, "edge_ids": ["e1"]},
            {"path_id": "higher", "path_kind": "seed_expansion", "score": 2.0, "edge_ids": ["e0"]},
        ],
    )

    assert [record["edge_id"] for record in selected_records] == ["e0"]
    assert list(selected_contexts) == ["/wiki/Alpha"]
    assert [path["path_id"] for path in selected_paths] == ["higher"]
    assert audit["full_record_count"] == 2
    assert audit["selected_record_count"] == 1


def test_oueg_short_answer_removes_common_labels_and_quotes():
    assert OnlineUnifiedEvidenceGraphBaseline._short_answer('Final Answer: "Mitre"') == "Mitre"


def test_oueg_seed_dfs_crosses_text_edges_and_scores_without_filtering():
    kg = OnlineKG()
    kg.register_table_structure(
        "Cities", [{"City": "Gaborone", "Population": "231,626"}],
        cell_links=[{"row_index": 0, "column_name": "City", "cell_value": "Gaborone", "url": "/wiki/Gaborone"}],
    )
    kg.register_passage("/wiki/Gaborone", "Gaborone has a population of 231,626.")
    kg.add_triple(Triple(
        "Botswana capital", "population", "231,626",
        Provenance("text", "/wiki/Gaborone", "has a population", source_group="rule_text"),
    ))
    records = OnlineUnifiedEvidenceGraphBaseline._complete_subgraph_records(
        kg.to_trace(), kg.path_edge_records(),
    )

    paths = OnlineUnifiedEvidenceGraphBaseline._seed_expansion_paths(
        "How many inhabitants does Gaborone have?", records,
    )

    assert paths
    assert all(path["role"] == "candidate" for path in paths)
    assert all(path["target_entity_type"] == "numeric" for path in paths)
    assert all("score_components" in path for path in paths)
    assert any(
        "Gaborone --linked_passage--> passage:/wiki/Gaborone" in path["steps"]
        and "passage:/wiki/Gaborone --mentions--> Botswana capital" in path["steps"]
        and "Botswana capital --population--> 231,626" in path["steps"]
        for path in paths
    )
    assert all(any(component == "grounded_edges" for component in path["score_components"]) for path in paths)


def test_oueg_bridge_lexical_signal_is_metadata_not_a_candidate_filter():
    kg = OnlineKG()
    kg.register_table_structure("League", [
        {"Club": "Gaborone United", "City": "Gaborone"},
        {"Club": "Other FC", "City": "Gaborone"},
    ])
    records = OnlineUnifiedEvidenceGraphBaseline._complete_subgraph_records(
        kg.to_trace(), kg.path_edge_records(),
    )
    paths = OnlineUnifiedEvidenceGraphBaseline._candidate_rows(
        "Which club is in Gaborone?", records,
    )

    assert {path["path_id"] for path in paths} == {"row_0", "row_1"}
    united = next(path for path in paths if path["anchor_entity"] == "Gaborone United")
    assert united["lexical_overlap_with_bridge_entity"] == 1.0
    assert all(path["role"] == "candidate" for path in paths)


def test_oueg_score_collision_marks_ambiguity_and_exposes_lexical_tiebreak():
    candidates = [
        {
            "path_id": "row_0", "anchor_entity": "Gaborone United",
            "bridge_entity": "Gaborone", "row_id": "row:0", "row_order_index": 0,
            "score": 10.0, "presentation_score": 11.0,
            "lexical_overlap_with_bridge_entity": 1.0,
        },
        {
            "path_id": "row_1", "anchor_entity": "Other FC",
            "bridge_entity": "Gaborone", "row_id": "row:1", "row_order_index": 1,
            "score": 10.0, "presentation_score": 10.0,
            "lexical_overlap_with_bridge_entity": 0.0,
        },
    ]

    assessment = OnlineUnifiedEvidenceGraphBaseline._ambiguity_assessment(
        "Which club is in Gaborone?", candidates,
    )

    assert assessment["is_ambiguous"] is True
    assert assessment["status"] == "SCORE_COLLISION_TIE"
    group = assessment["groups"][0]
    assert group["candidate_count"] == 2
    assert group["lexical_tiebreak"]["winner"] == "Gaborone United"
    assert assessment["selective_prediction"]["lexical_tiebreak_is_safe"] is True


def test_oueg_collision_expansion_covers_each_relevant_tied_row():
    example = DatasetExample(
        example_id="collision", question="Which jurisdiction has a rate of 21% and is named after a river?",
        table_rows=[{
            "table_name": "Rates",
            "rows": [
                {"Jurisdiction": "Alpha", "Rate": "21%"},
                {"Jurisdiction": "Beta", "Rate": "21%"},
                {"Jurisdiction": "Gamma", "Rate": "20%"},
            ],
            "cell_links": [
                {"row_index": 0, "column_name": "Jurisdiction", "url": "/wiki/Alpha"},
                {"row_index": 1, "column_name": "Jurisdiction", "url": "/wiki/Beta"},
                {"row_index": 2, "column_name": "Jurisdiction", "url": "/wiki/Gamma"},
            ],
        }],
        text_passages=[
            {"id": "/wiki/Alpha", "text": "Alpha has no river-name origin."},
            {"id": "/wiki/Beta", "text": "Beta is named after the Beta River."},
            {"id": "/wiki/Gamma", "text": "Gamma is unrelated."},
        ], answer="Beta",
    )
    ambiguity = {
        "groups": [
            {
                "bridge_entity": "21%", "status": "SCORE_COLLISION_TIE",
                "candidates": [
                    {"row_id": "table:Rates:row:0", "row_order_index": 0, "entity": "Alpha"},
                    {"row_id": "table:Rates:row:1", "row_order_index": 1, "entity": "Beta"},
                ],
            },
            {
                "bridge_entity": "20%", "status": "SCORE_COLLISION_TIE",
                "candidates": [{"row_id": "table:Rates:row:2", "row_order_index": 2, "entity": "Gamma"}],
            },
        ],
    }

    retrieved = {"text_passages": []}
    report = OnlineUnifiedEvidenceGraphBaseline(
        RAGConfig(collision_passage_budget=2),
    )._collision_linked_expansion(example, retrieved, ambiguity)

    assert report["triggered"] is True
    assert [item["row_index"] for item in report["candidate_rows"]] == [0, 1]
    assert report["added_source_ids"] == ["/wiki/Alpha", "/wiki/Beta"]
    assert [item["id"] for item in retrieved["text_passages"]] == ["/wiki/Alpha", "/wiki/Beta"]


def test_oueg_return_candidates_policy_abstains_without_llm(monkeypatch):
    kg = _kg_with_rows()

    class Builder:
        def build(self, retrieved):
            return kg

    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.two_stage_retrieve",
        lambda *args, **kwargs: {"retrieval_trace": {}},
    )
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "fake"})(),
    )
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.llm_call",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM must not be called")),
    )

    result = OnlineUnifiedEvidenceGraphBaseline(
        RAGConfig(max_output_tokens=32, ambiguity_policy="return_candidates"),
        kg_builder=Builder(),
    ).run(DatasetExample(
        example_id="ambiguous", question="Which club is in Gaborone?",
        table_rows=[], text_passages=[], answer="",
    ))

    assert result["abstained_for_ambiguity"] is True
    assert result["llm_calls"] == 0
    assert result["ambiguity"]["is_ambiguous"] is True
    assert result["answer"].startswith("Ambiguous: 2 candidates")


def test_oueg_prompt_injects_tie_break_hint_for_score_collision(monkeypatch):
    kg = _kg_with_rows()

    class Builder:
        def build(self, retrieved):
            return kg

    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.two_stage_retrieve",
        lambda *args, **kwargs: {"retrieval_trace": {}},
    )
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "fake"})(),
    )
    monkeypatch.setattr(
        OnlineUnifiedEvidenceGraphBaseline,
        "_ambiguity_assessment",
        classmethod(lambda cls, question, paths: {
            "is_ambiguous": True,
            "status": "SCORE_COLLISION_TIE",
            "groups": [],
            "selective_prediction": {"lexical_tiebreak_is_safe": False},
        }),
    )
    prompts = []
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.llm_call",
        lambda prompt, **kwargs: prompts.append(prompt) or "Club Early",
    )

    OnlineUnifiedEvidenceGraphBaseline(RAGConfig(
        max_output_tokens=32, use_lexical_tiebreak=True,
    ), kg_builder=Builder()).run(
        DatasetExample(
            example_id="tie", question="Which club is in Gaborone?",
            table_rows=[], text_passages=[], answer="",
        )
    )

    assert "Warning: More than one candidate satisfies the same bridge condition." in prompts[0]


def test_oueg_empty_first_response_uses_non_destructive_focus_handoff(monkeypatch):
    kg = _kg_with_rows()

    class Builder:
        def build(self, retrieved):
            return kg

    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.two_stage_retrieve",
        lambda *args, **kwargs: {"retrieval_trace": {}},
    )
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "fake"})(),
    )
    responses = iter(["", "Club Early"])
    prompts = []
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.llm_call",
        lambda prompt, **kwargs: prompts.append(prompt) or next(responses),
    )

    result = OnlineUnifiedEvidenceGraphBaseline(
        RAGConfig(max_output_tokens=32), kg_builder=Builder(),
    ).run(DatasetExample(
        example_id="empty", question="Which club is in Gaborone?",
        table_rows=[], text_passages=[], answer="Club Early",
    ))

    verification = result["adaptive_verification"]
    assert result["answer"] == "Club Early"
    assert result["llm_calls"] == 2
    assert verification["triggered"] is True
    assert verification["final_decision"] == "verified_after_focus"
    assert verification["handoff"]["origin"] == "empty_model_response"
    assert verification["handoff"]["non_destructive"] is True
    assert "L2 state capsule" in prompts[1]
    assert "do not assume you remember L1" in prompts[1]
    assert result["compact_oueg_payload"]


def test_oueg_ambiguous_need_focus_explains_blocker_then_uses_small_state_capsule(monkeypatch):
    """L2 repeats only sufficient candidate state; it does not assume L1 memory."""
    kg = _kg_with_rows()

    class Builder:
        def build(self, retrieved):
            return kg

    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.two_stage_retrieve",
        lambda *args, **kwargs: {"retrieval_trace": {}},
    )
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "fake"})(),
    )
    responses = iter([
        'NEED_FOCUS: {"candidates":["Club Late","Club Early"],'
        '"blocker_type":"candidate_collision",'
        '"bottleneck":"Both clubs share Gaborone as their bridge city.",'
        '"needed_check":"Compare the linked passage for the city-between-hills constraint."}',
        "FINAL_ANSWER: Club Early",
    ])
    prompts = []
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.llm_call",
        lambda prompt, **kwargs: prompts.append(prompt) or next(responses),
    )

    result = OnlineUnifiedEvidenceGraphBaseline(
        RAGConfig(max_output_tokens=32, prompt_path_budget=1), kg_builder=Builder(),
    ).run(DatasetExample(
        example_id="need-focus", question="Which club is in Gaborone?",
        table_rows=[], text_passages=[], answer="Club Early",
    ))

    verification = result["adaptive_verification"]
    assert result["answer"] == "Club Early"
    assert result["llm_calls"] == 2
    assert verification["triggered"] is True
    assert verification["final_decision"] == "verified_after_focus"
    assert verification["handoff"]["origin"] == "model_need_focus"
    assert verification["handoff"]["blocker_type"] == "candidate_collision"
    assert "linked passage" in verification["handoff"]["needed_check"]
    assert "UNRESOLVED:" in prompts[0]
    assert "never return a blank response" in prompts[0]
    assert "candidate_collision" in prompts[1]
    assert "L2 state capsule" in prompts[1]
    assert result["verification_evidence"]["mode"] == "delta_only"
    assert result["verification_evidence"]["l2_record_count"] < (
        result["verification_evidence"]["full_record_count"]
    )


def test_oueg_unresolved_response_keeps_a_diagnostic_instead_of_becoming_an_answer():
    answer, hint = OnlineUnifiedEvidenceGraphBaseline._parse_adaptive_response(
        'UNRESOLVED: {"blocker_type":"missing_link",'
        '"bottleneck":"No passage identifies the city.",'
        '"needed_check":"A linked city passage is required."}',
    )

    assert answer == ""
    assert hint["response_type"] == "unresolved"
    assert hint["blocker_type"] == "missing_link"
    assert hint["needed_check"] == "A linked city passage is required."


def test_oueg_evidence_path_audit_accepts_only_ids_visible_to_reader():
    audit = OnlineUnifiedEvidenceGraphBaseline._evidence_path_audit(
        'FINAL_ANSWER: Beta\nEVIDENCE_PATH: {"edges":["e7","e999"],"passages":["p2"]}',
        {"e7", "p2"},
    )

    assert audit["provided"] is True
    assert audit["selected_refs"] == ["e7", "p2"]
    assert audit["invalid_refs"] == ["e999"]


def test_oueg_diagnostic_focus_resolves_named_table_value_not_rank_anchor():
    baseline = OnlineUnifiedEvidenceGraphBaseline(RAGConfig())
    rows = [
        {
            "path_id": "row_0", "row_id": "table:Results:row:0", "row_order_index": 0,
            "anchor_entity": "1", "bridge_entity": "Other School",
            "sort_keys": {"Year": "2002", "Second place": "Other School"},
        },
        {
            "path_id": "row_1", "row_id": "table:Results:row:1", "row_order_index": 1,
            "anchor_entity": "2", "bridge_entity": "Stuartholme School",
            "sort_keys": {"Year": "2002", "Second place": "Stuartholme School"},
        },
    ]

    handoff = baseline._focus_handoff(
        "Who established the school that was the 2nd place winner?",
        {
            "response_type": "unresolved", "candidates": [], "blocker_type": "missing_link",
            "bottleneck": "history is missing",
            "needed_check": "founder information for Stuartholme School",
        },
        {"groups": []}, rows,
    )

    assert handoff["candidates"] == ["Stuartholme School"]
    assert handoff["focus_rows"][0]["row_id"] == "table:Results:row:1"
    assert "2" not in handoff["candidates"]


def test_oueg_diagnostic_focus_uses_ordinal_row_instead_of_first_rank_rows():
    baseline = OnlineUnifiedEvidenceGraphBaseline(RAGConfig())
    rows = [
        {
            "path_id": f"row_{index}", "row_id": f"table:Metro:row:{index}",
            "row_order_index": index, "anchor_entity": str(index + 1),
            "bridge_entity": f"Greater City {index + 1}",
            "sort_keys": {"Metropolitan area": f"Greater City {index + 1}"},
        }
        for index in range(10)
    ]
    rows[9]["bridge_entity"] = "Greater Querétaro"
    rows[9]["sort_keys"] = {"Metropolitan area": "Greater Querétaro"}

    handoff = baseline._focus_handoff(
        "How many boroughs does the 10th most populated metro area have?",
        {"response_type": "unresolved", "candidates": [], "blocker_type": "missing_link",
         "bottleneck": "missing borough count", "needed_check": "borough count for Greater Querétaro"},
        {"groups": []}, rows,
    )

    assert handoff["candidates"] == ["Greater Querétaro"]
    assert handoff["focus_rows"][0]["row_order_index"] == 9


def test_oueg_focus_augmentation_uses_links_from_grounded_row_not_rank_value():
    example = DatasetExample(
        example_id="focus-row-link", question="Who established Stuartholme School?",
        table_rows=[{
            "table_name": "Results",
            "rows": [{"Rank": "2", "School": "Stuartholme School"}],
            "cell_links": [
                {"row_index": 0, "column_name": "School", "url": "/wiki/Stuartholme_School"},
            ],
        }],
        text_passages=[{
            "id": "/wiki/Stuartholme_School",
            "text": "Stuartholme School was established by the Society of the Sacred Heart.",
        }], answer="Society of the Sacred Heart",
    )
    handoff = {
        "blocker_type": "missing_link", "needed_check": "founder of Stuartholme School",
        "candidates": ["Stuartholme School"],
        "focus_rows": [{
            "entity": "Stuartholme School", "row_id": "table:Results:row:0",
            "row_order_index": 0,
        }],
    }
    retrieved = {"text_passages": []}

    report = OnlineUnifiedEvidenceGraphBaseline(RAGConfig(
        focus_passage_budget_per_candidate=1, focus_query_fallback_budget=1,
    ))._focus_evidence_augmentation(example, retrieved, handoff)

    assert report["candidate_sources"] == {"Stuartholme School": ["/wiki/Stuartholme_School"]}
    assert report["linked_source_ids"]["Stuartholme School"] == ["/wiki/Stuartholme_School"]
    assert [item["id"] for item in retrieved["text_passages"]] == ["/wiki/Stuartholme_School"]


def test_oueg_l2_augments_missing_linked_text_for_each_focus_candidate(monkeypatch):
    """L2 fetches a balanced semantic delta only after an L1 missing-link report."""
    rows = [
        {"Jurisdiction": "Alpha", "Rate": "21%"},
        {"Jurisdiction": "Beta", "Rate": "21%"},
    ]

    class Builder:
        def build(self, retrieved):
            kg = OnlineKG()
            kg.register_table_structure("Rates", rows, cell_links=[
                {"row_index": 0, "column_name": "Jurisdiction", "cell_value": "Alpha", "url": "/wiki/Alpha"},
                {"row_index": 1, "column_name": "Jurisdiction", "cell_value": "Beta", "url": "/wiki/Beta"},
            ])
            for passage in retrieved.get("text_passages", []):
                source_id, text = passage["id"], passage["text"]
                kg.register_passage(source_id, text)
                if source_id == "/wiki/Alpha":
                    kg.add_triple(Triple(
                        "Alpha", "origin", "not named after a river",
                        Provenance("text", source_id, text, source_group="rule_text"),
                    ))
                if source_id == "/wiki/Beta":
                    kg.add_triple(Triple(
                        "Beta", "named_after", "Beta River",
                        Provenance("text", source_id, text, source_group="rule_text"),
                    ))
            return kg

    example = DatasetExample(
        example_id="l2-augment",
        question="Which jurisdiction has a 21% rate and is named after a river?",
        table_rows=[{
            "table_name": "Rates", "rows": rows,
            "cell_links": [
                {"row_index": 0, "column_name": "Jurisdiction", "url": "/wiki/Alpha"},
                {"row_index": 1, "column_name": "Jurisdiction", "url": "/wiki/Beta"},
            ],
        }],
        text_passages=[
            {"id": "/wiki/Alpha", "text": "Alpha is not named after a river."},
            {"id": "/wiki/Beta", "text": "Beta is named after the Beta River."},
        ],
        answer="Beta",
    )
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.two_stage_retrieve",
        lambda *args, **kwargs: {"retrieval_trace": {}, "text_passages": []},
    )
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "fake"})(),
    )
    responses = iter([
        'NEED_FOCUS: {"candidates":["Alpha","Beta"],"blocker_type":"missing_link",'
        '"bottleneck":"The river-origin passages are absent.",'
        '"needed_check":"Retrieve the linked origin passage for each jurisdiction."}',
        "FINAL_ANSWER: Beta",
    ])
    prompts = []
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.llm_call",
        lambda prompt, **kwargs: prompts.append(prompt) or next(responses),
    )

    result = OnlineUnifiedEvidenceGraphBaseline(RAGConfig(
        max_output_tokens=32,
        use_path_focused_prompt=False,
        use_collision_evidence_expansion=False,
        focus_passage_budget_per_candidate=1,
    ), kg_builder=Builder()).run(example)

    augmentation = result["focus_evidence_augmentation"]
    assert result["answer"] == "Beta"
    assert result["llm_calls"] == 2
    assert augmentation["triggered"] is True
    assert augmentation["candidate_sources"] == {
        "Alpha": ["/wiki/Alpha"], "Beta": ["/wiki/Beta"],
    }
    assert augmentation["added_source_ids"] == ["/wiki/Alpha", "/wiki/Beta"]
    assert result["verification_evidence"]["mode"] == "delta_only"
    assert result["verification_evidence"]["augmentation_applied"] is True
    assert "Alpha is not named after a river" not in prompts[0]
    assert "Alpha is not named after a river" in prompts[1]
    assert "Beta is named after the Beta River" in prompts[1]
    handoff = result["adaptive_verification"]["handoff"]
    assert handoff["semantic_delta"]
    assert all("score" not in item for item in handoff["candidate_provenance"])
    capsule = result["adaptive_verification"]["l2_state_capsule"]
    assert capsule["question"] == example.question
    assert [packet["entity"] for packet in capsule["candidate_packets"]] == ["Alpha", "Beta"]
    assert all(packet["row_binding"] for packet in capsule["candidate_packets"])


@pytest.mark.parametrize(
    ("uniquely_river_named", "second_response", "expected_answer", "expected_decision"),
    [
        (
            True,
            "FINAL_ANSWER: Beta",
            "Beta",
            "verified_after_focus",
        ),
        (
            False,
            'UNRESOLVED: {"blocker_type":"conflicting_evidence",'
            '"bottleneck":"Both jurisdictions satisfy the river-origin condition.",'
            '"needed_check":"A fact that uniquely selects one jurisdiction is required."}',
            "",
            "grounded_abstention",
        ),
    ],
    ids=["semantic-text-resolves-collision", "semantic-text-preserves-logical-ambiguity"],
)
def test_oueg_two_case_focus_experiment(monkeypatch, uniquely_river_named, second_response, expected_answer, expected_decision):
    """Exercise the proposed full-OUEG L1 → semantic L2 policy on two outcomes."""
    kg = _kg_with_rate_collision(uniquely_river_named=uniquely_river_named)

    class Builder:
        def build(self, retrieved):
            return kg

    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.two_stage_retrieve",
        lambda *args, **kwargs: {"retrieval_trace": {}},
    )
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.get_provider",
        lambda: type("Provider", (), {"name": "fake", "model": "fake"})(),
    )
    responses = iter([
        'NEED_FOCUS: {"candidates":["Alpha","Beta"],'
        '"blocker_type":"candidate_collision",'
        '"bottleneck":"Both rows have the same 21% rate.",'
        '"needed_check":"Compare each jurisdiction text for whether it is named after a river."}',
        second_response,
    ])
    prompts = []
    monkeypatch.setattr(
        "src.baselines.online_unified_evidence_graph.llm_call",
        lambda prompt, **kwargs: prompts.append(prompt) or next(responses),
    )

    result = OnlineUnifiedEvidenceGraphBaseline(
        # This is the proposed L1 policy: no path-focused pruning.
        RAGConfig(max_output_tokens=32, use_path_focused_prompt=False),
        kg_builder=Builder(),
    ).run(DatasetExample(
        example_id="rate-collision",
        question="Which jurisdiction has a 21% rate and is named after a river?",
        table_rows=[], text_passages=[], answer=expected_answer,
    ))

    assert result["ambiguity"]["status"] == "SCORE_COLLISION_TIE"
    assert result["llm_calls"] == 2
    assert result["answer"] == expected_answer
    assert result["adaptive_verification"]["final_decision"] == expected_decision
    assert result["answer_time_evidence"]["enabled"] is False
    assert "Alpha is" in prompts[0] and "Beta is named after" in prompts[0]
    assert "Compare each jurisdiction text" in prompts[1]
    assert result["verification_evidence"]["mode"] == "delta_only"
    assert result["verification_evidence"]["l2_record_count"] < (
        result["verification_evidence"]["full_record_count"]
    )
    if expected_answer:
        assert result["adaptive_verification"]["second_diagnostic"] is None
    else:
        assert result["adaptive_verification"]["second_diagnostic"]["blocker_type"] == "conflicting_evidence"


def test_oueg_need_focus_parser_keeps_only_a_valid_handoff_shape():
    answer, hint = OnlineUnifiedEvidenceGraphBaseline._parse_adaptive_response(
        'NEED_FOCUS: {"candidates":["Alpha","Beta"],"bottleneck":"check origin"}',
    )

    assert answer == ""
    assert hint["candidates"] == ["Alpha", "Beta"]
    assert hint["bottleneck"] == "check origin"



def test_oueg_ablation_controls_flatten_record_nodes_and_keep_verbatim_payload():
    kg = OnlineKG()
    kg.register_table_structure("T", [{"Subject": "Alpha", "Value": "Beta"}])
    records = OnlineUnifiedEvidenceGraphBaseline._complete_subgraph_records(
        kg.to_trace(), kg.path_edge_records(),
    )

    flattened = OnlineUnifiedEvidenceGraphBaseline._without_record_nodes(records)

    assert not any(edge.get("relation") == "has_record" for edge in flattened)
    assert not any(
        ":row:" in str(edge.get("head")) or ":row:" in str(edge.get("tail"))
        for edge in flattened
    )
    assert any(
        edge.get("head") == "Alpha" and edge.get("tail") == "Beta"
        for edge in flattened
    )

    payload = _VerbatimOUEGPromptBuilder.build(
        question="Which value belongs to Alpha?", records=flattened,
        contexts_by_source_id={}, suggested_paths=[], ordering_hint={},
        ambiguity={}, path_generation={},
    )
    assert payload["stats"]["compression_enabled"] is False
    assert payload["payload"]["records"] == flattened
