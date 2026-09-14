import json

from src.baselines.metrics import hitab_denotation_match, hitab_strict_denotation_match
from src.datasets.hitab import hierarchical_table_to_rows, load_hitab


def test_hierarchical_table_materializes_full_header_paths():
    table = {
        "texts": [
            ["season", "rushing", ""],
            ["", "att", "yds"],
            ["2016", "51", "149"],
        ],
        "top_header_rows_num": 2,
        "left_header_columns_num": 1,
        "merged_regions": [{
            "first_row": 0, "last_row": 0, "first_column": 1, "last_column": 2,
        }],
        "left_root": {"row_index": -1, "column_index": -1, "children": [
            {"row_index": 2, "column_index": 0, "children": []},
        ]},
    }
    rows = hierarchical_table_to_rows(table)
    assert rows == [{"row_path": "2016", "rushing__att": "51", "rushing__yds": "149"}]


def test_hierarchical_rows_keep_repeated_years_in_distinct_groups():
    table = {
        "texts": [
            ["year", "value"], ["current", ""], ["2012", "100"],
            ["constant", ""], ["2012", "90"],
        ],
        "top_header_rows_num": 1, "left_header_columns_num": 1,
        "merged_regions": [],
        "left_root": {"row_index": -1, "column_index": -1, "children": [{
            "row_index": 1, "column_index": 0, "children": [
                {"row_index": 2, "column_index": 0, "children": []},
                {"row_index": 3, "column_index": 0, "children": [
                    {"row_index": 4, "column_index": 0, "children": []},
                ]},
            ],
        }]},
    }
    rows = hierarchical_table_to_rows(table)
    assert rows[0]["row_path"] == "current / 2012"
    assert rows[-1]["row_path"] == "current / constant / 2012"


def test_hitab_loader_does_not_leak_sub_sentence(tmp_path):
    samples = tmp_path / "dev.jsonl"
    tables = tmp_path / "tables"
    tables.mkdir()
    samples.write_text(json.dumps({
        "id": "q", "table_id": "t", "question": "How many?", "answer": [51.0],
        "sub_sentence": "The answer is 51.",
    }) + "\n")
    (tables / "t.json").write_text(json.dumps({
        "texts": [["year", "value"], ["2016", "51"]],
        "top_header_rows_num": 1, "left_header_columns_num": 1,
        "merged_regions": [], "title": "demo",
    }))
    example = next(load_hitab(samples, tables_dir=tables))
    assert example.answer == 51.0
    assert example.text_passages == []
    assert example.table_rows[0]["deterministic_only"] is True
    assert "answer" not in str(example.pipeline_inputs()).lower()


def test_hitab_denotation_numeric_tolerance():
    assert hitab_denotation_match([51.0], "51") == 1.0
    assert hitab_denotation_match(1.11111, "1.111111") == 1.0
    assert hitab_denotation_match(51, "52") == 0.0


def test_hitab_ratio_and_percentage_are_semantically_equivalent():
    assert hitab_denotation_match(0.876264, 87.62636269360156) == 1.0
    assert hitab_strict_denotation_match(0.876264, 87.62636269360156) == 0.0
