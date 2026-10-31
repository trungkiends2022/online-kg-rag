import json

import pytest

from src.datasets.finqa import load_finqa
from src.datasets.hybridqa import load_hybridqa
from src.datasets.ottqa import load_ottqa


def _write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_load_hybridqa_embedded_table(tmp_path):
    split = tmp_path / "dev.json"
    _write_json(split, [{
        "question_id": "q1",
        "question": "Where was the winner born?",
        "answer_text": "Hanoi",
        "table_id": "t1",
        "table": {
            "title": "Winners",
            "header": ["Winner", "Year"],
            "data": [[
                {"value": "An", "urls": [{"url": "An", "summary": "An was born in Hanoi."}]},
                {"value": "2020", "urls": []},
            ]],
        },
    }])

    example = next(load_hybridqa(split))

    assert example.example_id == "q1"
    assert example.table_rows[0]["rows"] == [{"Winner": "An", "Year": "2020"}]
    assert example.table_rows[0]["cell_links"] == [{
        "row_index": 0,
        "column_name": "Winner",
        "cell_value": "An",
        "url": "An",
    }]
    assert example.text_passages == [{"id": "An", "text": "An was born in Hanoi."}]
    assert example.answer == "Hanoi"


def test_load_hybridqa_official_separate_files(tmp_path):
    split = tmp_path / "dev.json"
    tables = tmp_path / "tables_tok"
    passages = tmp_path / "request_tok"
    tables.mkdir()
    passages.mkdir()
    _write_json(split, [{"question_id": "q1", "question": "Q?", "table_id": "t1"}])
    _write_json(tables / "t1.json", {"header": ["Name"], "data": [["Alpha"]]})
    _write_json(passages / "t1.json", {"Alpha": ["Alpha", "is", "a", "company."]})

    example = next(load_hybridqa(split, tables_dir=tables, passages_dir=passages))

    assert example.table_rows[0]["rows"] == [{"Name": "Alpha"}]
    assert example.text_passages[0]["text"] == "Alpha is a company."


def test_hybridqa_requires_tables_dir_for_official_split(tmp_path):
    split = tmp_path / "dev.json"
    _write_json(split, [{"question": "Q?", "table_id": "missing"}])

    with pytest.raises(ValueError, match="tables-dir"):
        next(load_hybridqa(split))


def test_load_ottqa_uses_official_separate_table_and_passages(tmp_path):
    split = tmp_path / "dev.json"
    tables = tmp_path / "traindev_tables_tok"
    passages = tmp_path / "traindev_request_tok"
    tables.mkdir()
    passages.mkdir()
    _write_json(split, [{
        "question_id": "ott-1", "question": "Who made it?", "answer-text": "Ada",
        "table_id": "table-1",
    }])
    _write_json(tables / "table-1.json", {
        "title": "Credits", "header": [["Work", []], ["Creator", []]],
        "data": [[["Example", ["/wiki/Example"]], ["Ada", []]]],
    })
    _write_json(passages / "table-1.json", {"/wiki/Example": "Example was made by Ada."})

    example = next(load_ottqa(split, tables_dir=tables, passages_dir=passages))

    assert example.example_id == "ott-1"
    assert example.table_rows[0]["rows"] == [{"Work": "Example", "Creator": "Ada"}]
    assert example.text_passages == [{"id": "/wiki/Example", "text": "Example was made by Ada."}]
    assert example.metadata["evaluation_context"] == "oracle_train_dev_table_and_passages"


def test_load_finqa_retains_gold_program(tmp_path):
    split = tmp_path / "dev.json"
    _write_json(split, [{
        "id": "report-1",
        "pre_text": ["Revenue increased."],
        "post_text": ["End of report."],
        "table": [["Year", "Revenue"], ["2023", "100"]],
        "qa": {
            "question": "What was revenue?",
            "answer": "100",
            "exe_ans": 100,
            "program": "add(100, 0)",
            "gold_inds": {"table_1": "2023 100"},
        },
    }])

    example = next(load_finqa(split))

    assert example.table_rows[0]["rows"] == [{"Year": "2023", "Revenue": "100"}]
    assert len(example.text_passages) == 2
    assert example.answer == 100
    assert example.metadata["program"] == "add(100, 0)"
    assert example.metadata["table_format"] == "official"


def test_load_finqa_can_select_raw_hierarchical_table(tmp_path):
    split = tmp_path / "dev.json"
    _write_json(split, [{
        "id": "report-raw",
        "pre_text": [], "post_text": [],
        "table": [["Official", "Value"], ["row", "1"]],
        "table_ori": [["Raw", "Value"], ["row", "2"]],
        "qa": {"question": "Q?", "exe_ans": 2, "program": "add(2, 0)"},
    }])
    example = next(load_finqa(split, table_format="raw"))
    assert example.table_rows[0]["rows"][0] == {"Raw": "row", "Value": "2"}
    assert example.metadata["table_format"] == "raw"
