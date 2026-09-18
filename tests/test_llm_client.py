import pytest

from src.llm.client import _parse_json_list


def test_parse_json_list_accepts_provider_prose_wrapper():
    assert _parse_json_list('Here is the result: [{"head": "A"}]') == [{"head": "A"}]


def test_parse_json_list_rejects_truncated_array():
    with pytest.raises(ValueError):
        _parse_json_list('[{"head": "A"}')
