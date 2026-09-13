from src.datasets.common import matrix_to_rows


def test_matrix_to_rows_expands_finqa_two_level_header():
    matrix = [
        ["", "2002", "2001"],
        ["Quarter Ended", "High", "Low", "Dividend", "High", "Low", "Dividend"],
        ["March 31", "26.50", "22.92", ".450", "25.44", "21.85", ".43"],
    ]
    assert matrix_to_rows(matrix) == [{
        "Quarter Ended": "March 31",
        "2002_High": "26.50",
        "2002_Low": "22.92",
        "2002_Dividend": ".450",
        "2001_High": "25.44",
        "2001_Low": "21.85",
        "2001_Dividend": ".43",
    }]


def test_matrix_to_rows_never_overwrites_duplicate_columns():
    rows = matrix_to_rows([
        ["Period", "High", "Low", "High", "Low"],
        ["Q1", "10", "5", "20", "7"],
    ])
    assert len(rows[0]) == 5
    assert list(rows[0].values()) == ["Q1", "10", "5", "20", "7"]


def test_matrix_to_rows_preserves_cells_wider_than_header():
    rows = matrix_to_rows([["Name", "Value"], ["A", "1", "extra"]])
    assert rows[0]["column_2"] == "extra"
