#!/usr/bin/env python3
"""Run the two-case OUEG focus experiment through the configured provider.

This deliberately uses only synthetic evidence.  Set the provider/model at
invocation time, for example:

    LLM_PROVIDER=openrouter OPENROUTER_MODEL=openai/gpt-oss-120b \
      python scripts/run_oueg_two_case_openrouter.py
"""

from __future__ import annotations

import json
from unittest.mock import patch

from src.baselines.online_unified_evidence_graph import OnlineUnifiedEvidenceGraphBaseline
from src.baselines.rag_variants import RAGConfig
from src.datasets.schema import DatasetExample
from src.kg.online_kg import OnlineKG
from src.kg.schema import Provenance, Triple


def build_kg(*, uniquely_river_named: bool) -> OnlineKG:
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


class StaticBuilder:
    def __init__(self, kg: OnlineKG):
        self.kg = kg

    def build(self, retrieved: dict) -> OnlineKG:
        return self.kg


class RetrievedTextBuilder:
    """Build the same table graph, but expose passage facts only if retrieved."""

    def build(self, retrieved: dict) -> OnlineKG:
        kg = OnlineKG()
        rows = [
            {"Jurisdiction": "Alpha", "Rate": "21%"},
            {"Jurisdiction": "Beta", "Rate": "21%"},
        ]
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


def run_case(name: str, *, uniquely_river_named: bool) -> dict:
    with patch(
        "src.baselines.online_unified_evidence_graph.two_stage_retrieve",
        lambda *args, **kwargs: {"retrieval_trace": {}},
    ):
        result = OnlineUnifiedEvidenceGraphBaseline(
            # L1 receives the complete compact OUEG, as proposed.
            RAGConfig(
                # GPT-OSS reasoning can consume part of a small completion
                # budget before emitting the structured protocol response.
                max_output_tokens=1024,
                temperature=0.0,
                use_path_focused_prompt=False,
            ),
            kg_builder=StaticBuilder(build_kg(uniquely_river_named=uniquely_river_named)),
        ).run(DatasetExample(
            example_id=name,
            question="Which jurisdiction has a 21% rate and is named after a river?",
            table_rows=[],
            text_passages=[],
            answer="Beta" if uniquely_river_named else "",
        ))
    verification = result["adaptive_verification"]
    return {
        "case": name,
        "answer": result["answer"],
        "llm_calls": result["llm_calls"],
        "ambiguity_status": result["ambiguity"]["status"],
        "decision": verification["final_decision"],
        "first_response": verification["first_response"],
        "handoff": verification["handoff"],
        "second_response": verification["second_response"],
        "second_diagnostic": verification.get("second_diagnostic"),
        "verification_evidence": result["verification_evidence"],
        "focus_evidence_augmentation": result["focus_evidence_augmentation"],
    }


def run_missing_link_case() -> dict:
    """L1 has the full table OUEG but no passage facts; L2 may add both links."""
    rows = [
        {"Jurisdiction": "Alpha", "Rate": "21%"},
        {"Jurisdiction": "Beta", "Rate": "21%"},
    ]
    example = DatasetExample(
        example_id="missing-link-augmentation",
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
    with patch(
        "src.baselines.online_unified_evidence_graph.two_stage_retrieve",
        lambda *args, **kwargs: {"retrieval_trace": {}, "text_passages": []},
    ):
        result = OnlineUnifiedEvidenceGraphBaseline(
            RAGConfig(
                max_output_tokens=1024,
                temperature=0.0,
                use_path_focused_prompt=False,
                # Keep the text absent at L1 so this specifically exercises
                # the diagnostic-triggered augmentation path.
                use_collision_evidence_expansion=False,
                focus_passage_budget_per_candidate=1,
            ),
            kg_builder=RetrievedTextBuilder(),
        ).run(example)
    verification = result["adaptive_verification"]
    return {
        "case": "missing-link-augmentation",
        "answer": result["answer"],
        "llm_calls": result["llm_calls"],
        "ambiguity_status": result["ambiguity"]["status"],
        "decision": verification["final_decision"],
        "first_response": verification["first_response"],
        "handoff": verification["handoff"],
        "second_response": verification["second_response"],
        "second_diagnostic": verification.get("second_diagnostic"),
        "verification_evidence": result["verification_evidence"],
        "focus_evidence_augmentation": result["focus_evidence_augmentation"],
    }


def main() -> None:
    outcomes = [
        run_case("semantic-resolution", uniquely_river_named=True),
        run_missing_link_case(),
    ]
    print(json.dumps(outcomes, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
