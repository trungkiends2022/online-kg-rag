import platform
import pytest

from src.kg.online_kg import OnlineKG
from src.kg.schema import Triple, Provenance
from src.execution.sandbox import SandboxExecutor


def _make_kg():
    kg = OnlineKG()
    kg.add_triple(Triple("Alpha Tech", "sector", "Technology", Provenance("table", "t1")))
    kg.add_triple(Triple("Beta Foods", "sector", "Consumer", Provenance("table", "t1")))
    return kg


def test_successful_execution():
    kg = _make_kg()
    code = "result = kg.get_neighbors('Alpha Tech', 'sector')"
    res = SandboxExecutor().run(code, kg)
    assert res.success
    assert res.value == ["Technology"]
    assert not res.is_empty
    assert res.accessed_edges == 1
    assert res.evidence[0].source_type == "table"
    assert res.evidence[0].source_id == "t1"
    assert res.evidence[0].head == "Alpha Tech"
    assert res.evidence[0].tail == "Technology"


def test_empty_result():
    kg = _make_kg()
    code = "result = kg.get_neighbors('Nonexistent', 'sector')"
    res = SandboxExecutor().run(code, kg)
    assert res.success
    assert res.is_empty
    assert res.evidence == ()


def test_reverse_lookup_records_evidence():
    kg = _make_kg()
    res = SandboxExecutor().run(
        "result = kg.get_sources('Technology', 'sector')", kg
    )
    assert res.value == ["Alpha Tech"]
    assert len(res.evidence) == 1
    assert res.evidence[0].relation == "sector"


def test_generated_function_can_access_kg():
    kg = _make_kg()
    code = """
def lookup(entity):
    return kg.get_neighbors(entity, 'sector')
result = lookup('Alpha Tech')
"""
    res = SandboxExecutor().run(code, kg)
    assert res.success
    assert res.value == ["Technology"]


def test_runtime_error_caught():
    kg = _make_kg()
    code = "result = 1 / 0"
    res = SandboxExecutor().run(code, kg)
    assert not res.success
    assert "ZeroDivisionError" in res.error


def test_import_blocked():
    kg = _make_kg()
    code = "import os\nresult = os.listdir('.')"
    res = SandboxExecutor().run(code, kg)
    assert not res.success  # __import__ không có trong SAFE_BUILTINS


@pytest.mark.skipif(platform.system() == "Windows", reason="signal.SIGALRM not available on Windows")
def test_timeout():
    kg = _make_kg()
    code = "while True:\n    pass"
    res = SandboxExecutor().run(code, kg, timeout_sec=1)
    assert not res.success
    assert "timed out" in res.error
