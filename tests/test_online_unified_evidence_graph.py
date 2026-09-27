from src.baselines.online_unified_evidence_graph import OnlineUnifiedEvidenceGraphBaseline
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

    assert hint["detected_signal"] == "temporal_first"
    assert hint["sort_by_column"] == "Formed"
    assert [path["path_id"] for path in ordered] == ["row_1", "row_2", "row_0"]
    assert {path["path_id"] for path in ordered} == {"row_0", "row_1", "row_2"}


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
    assert "`rows` retains every table row" in prompts[0]
    assert result["prompt_compression"]["all_edges_represented"] is True
    assert "nodes" not in result["compact_oueg_payload"]


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

    OnlineUnifiedEvidenceGraphBaseline(RAGConfig(max_output_tokens=32), kg_builder=Builder()).run(
        DatasetExample(
            example_id="tie", question="Which club is in Gaborone?",
            table_rows=[], text_passages=[], answer="",
        )
    )

    assert "Warning: More than one candidate satisfies the same bridge condition." in prompts[0]
