from src.kg.online_kg import OnlineKG
from src.kg.schema import Triple, Provenance


def _triple(h, r, t, source="text"):
    return Triple(h, r, t, Provenance(source, "src1", "..."))


def test_add_triple_and_neighbors():
    kg = OnlineKG()
    kg.add_triple(_triple("Alpha Tech", "sector", "Technology"))
    assert kg.get_neighbors("Alpha Tech") == ["Technology"]
    assert kg.get_neighbors("Alpha Tech", relation="sector") == ["Technology"]
    assert kg.get_neighbors("Alpha Tech", relation="other") == []


def test_get_relations():
    kg = OnlineKG()
    kg.add_triple(_triple("Alpha Tech", "sector", "Technology"))
    kg.add_triple(_triple("Alpha Tech", "revenue", "120"))
    assert kg.get_relations("Alpha Tech") == ["revenue", "sector"]


def test_merge_entities():
    kg = OnlineKG()
    kg.add_triple(_triple("alpha tech", "sector", "Technology"))
    kg.add_triple(_triple("Alpha Tech", "revenue", "120"))
    kg.merge_entities("Alpha Tech", ["alpha tech"])
    assert set(kg.get_relations("Alpha Tech")) == {"revenue", "sector"}
    assert "alpha tech" not in kg.graph


def test_is_empty():
    kg = OnlineKG()
    assert kg.is_empty()
    kg.add_triple(_triple("A", "r", "B"))
    assert not kg.is_empty()


def test_provenance_tracking():
    kg = OnlineKG()
    kg.add_triple(_triple("Alpha Tech", "sector", "Technology", source="table"))
    prov = kg.get_provenance("Alpha Tech", "Technology")
    assert len(prov) == 1
    assert prov[0].source_type == "table"
