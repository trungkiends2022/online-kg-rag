from src.kg.online_kg import OnlineKG
from src.kg.schema import Triple, Provenance
from src.kg.normalization import EntityResolver, normalize_key


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


def test_reverse_lookup_and_relation_normalization():
    kg = OnlineKG()
    kg.add_triple(_triple("Karim Bencherifa", "hasNationality", "Morocco"))
    kg.add_triple(_triple("Karim Bencherifa", "date of birth", "15 February 1968"))

    assert kg.get_neighbors("Karim Bencherifa", "has_nationality") == ["Morocco"]
    assert kg.get_neighbors("Karim Bencherifa", "birthDate") == ["15 February 1968"]
    assert kg.get_sources("15 February 1968", "birth_date") == ["Karim Bencherifa"]
    assert kg.get_relations("Karim Bencherifa") == ["birth_date", "nationality"]


def test_relation_ontology_and_fuzzy_typo_normalization():
    kg = OnlineKG()
    kg.add_triple(_triple("Person", "current profession", "coach"))
    kg.add_triple(_triple("Person", "nationalty", "Morocco"))
    assert kg.get_relations("Person") == ["current_occupation", "nationality"]


def test_entity_resolution_three_tiers_and_audit_log():
    kg = OnlineKG()
    kg.add_triple(_triple("Hồ Chí Minh", "birthDate", "19 May 1890"))
    kg.add_triple(_triple("ho chi minh", "occupation", "President"))
    kg.add_triple(_triple("Person", "nationality", "Moroccan"))
    kg.add_triple(_triple("IBM", "industry", "Technology"))
    kg.add_triple(_triple("International Business Machines", "founded", "1911"))

    def fake_embedding_similarity(left, right):
        pair = {normalize_key(left), normalize_key(right)}
        return 0.97 if pair == {"ibm", "international business machines"} else 0.0

    EntityResolver(similarity_fn=fake_embedding_similarity).resolve(kg)

    assert kg.get_neighbors("Bác Hồ", "birth_date") == ["19 May 1890"]
    assert kg.get_neighbors("HO CHI MINH", "occupation") == ["President"]
    assert kg.get_sources("Morocco", "nationality") == ["Person"]
    assert "IBM" not in kg.graph
    assert kg.get_neighbors("IBM", "industry") == ["Technology"]
    assert {event["tier"] for event in kg.resolution_log} == {"lexical", "alias", "semantic"}


def test_semantic_resolution_does_not_merge_date_literals():
    kg = OnlineKG()
    kg.add_triple(_triple("A", "date", "15 February 1968"))
    kg.add_triple(_triple("B", "date", "16 February 1968"))
    EntityResolver(similarity_fn=lambda _left, _right: 1.0).resolve(kg)
    assert "15 February 1968" in kg.graph
    assert "16 February 1968" in kg.graph


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
