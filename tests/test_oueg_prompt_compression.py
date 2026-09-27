from src.baselines.online_unified_evidence_graph import OnlineUnifiedEvidenceGraphBaseline
from src.baselines.oueg_prompt_compression import (
    CompactOUEGPromptBuilder,
    OUEGPromptCompressionConfig,
)
from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple


def _records():
    kg = OnlineKG()
    kg.register_table_structure(
        "League", [
            {"Club": "Gaborone United", "City": "Gaborone", "Position": "6th"},
            {"Club": "Other FC", "City": "Gaborone", "Position": "7th"},
        ],
        cell_links=[
            {"row_index": index, "column_name": "City", "cell_value": "Gaborone", "url": "/wiki/Gaborone"}
            for index in range(2)
        ],
    )
    kg.register_passage("/wiki/Gaborone", "Gaborone is the capital of Botswana.")
    kg.add_triple(Triple(
        "Gaborone", "population", "231,626",
        Provenance("text", "/wiki/Gaborone", "population", source_group="rule_text"),
    ))
    records = OnlineUnifiedEvidenceGraphBaseline._complete_subgraph_records(
        kg.to_trace(), kg.path_edge_records(),
    )
    paths = OnlineUnifiedEvidenceGraphBaseline._candidate_rows(
        "Which club is in Gaborone?", records,
    )
    return kg, records, paths


def test_compact_prompt_keeps_every_edge_and_uses_row_records_without_nodes():
    kg, records, paths = _records()
    result = CompactOUEGPromptBuilder().build(
        question="Which club is in Gaborone?", records=records,
        contexts_by_source_id=kg.text_contexts, suggested_paths=paths,
        ordering_hint={"detected_signal": "none"}, ambiguity={}, path_generation={},
    )

    payload = result["payload"]
    assert result["stats"]["all_edges_represented"] is True
    assert result["stats"]["full_edge_count"] == len(records)
    assert "nodes" not in payload
    assert len(payload["rows"]) == 2
    assert payload["rows"][0]["edges"]
    assert any(edge["r"] == "population" for edge in payload["edges"])
    assert set(payload["contexts"]) == {"p0"}
    assert all("score_components" not in path for path in payload["paths"])


def test_extractive_mode_only_shrinks_long_contexts_and_marks_them():
    kg, records, paths = _records()
    long_text = " ".join([
        "Gaborone is a city in Botswana.",
        "It has many businesses and roads.",
        "Its population is 231,626 inhabitants.",
        "The city has several parks and markets.",
        "It is the capital city.",
    ])
    result = CompactOUEGPromptBuilder(OUEGPromptCompressionConfig(
        context_mode="extractive", snippet_min_chars=20, snippet_max_sentences=2,
    )).build(
        question="What is the population of Gaborone?", records=records,
        contexts_by_source_id={"/wiki/Gaborone": {"source_id": "/wiki/Gaborone", "text": long_text}},
        suggested_paths=paths, ordering_hint={}, ambiguity={}, path_generation={},
    )

    context = result["payload"]["contexts"]["p0"]
    assert context["extractive_snippet"] is True
    assert len(context["text"]) < len(long_text)
    assert result["stats"]["extractive_context_count"] == 1
