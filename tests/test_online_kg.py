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


def test_full_trace_serializes_edges_provenance_and_aliases():
    kg = OnlineKG()
    kg.add_triple(Triple(
        "Alpha", "value", "120",
        Provenance("table", "t1", "120", row_index=2, column_name="Revenue"),
    ))
    kg.entity_aliases["alpha"] = "Alpha"
    trace = kg.to_trace()
    assert trace["nodes"] == ["Alpha", "120"]
    assert trace["edges"][0]["relation"] == "value"
    assert trace["edges"][0]["provenance"]["row_index"] == 2
    assert trace["aliases"] == {"alpha": "Alpha"}


def test_rejects_extractor_self_loop():
    kg = OnlineKG()
    kg.add_triple(_triple("Liverpool Football Club", "located_in", "Liverpool Football Club"))

    assert kg.is_empty()
    assert kg.summary()["num_rejected_triples"] == 1
    assert kg.rejection_log[0]["reason"] == "self_loop"


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


def test_semantic_resolution_does_not_merge_hierarchical_period_paths():
    kg = OnlineKG()
    kg.add_triple(_triple("constant dollars / 2012", "value", "100"))
    kg.add_triple(_triple("constant dollars / 2013", "value", "90"))
    EntityResolver(similarity_fn=lambda _left, _right: 1.0).resolve(kg)
    assert "constant dollars / 2012" in kg.graph
    assert "constant dollars / 2013" in kg.graph


def test_semantic_resolution_does_not_merge_hierarchical_rows_with_different_years():
    kg = OnlineKG()
    left = "constant dollars / 2012"
    right = "constant dollars / 2013"
    kg.add_triple(_triple(left, "value", "100"))
    kg.add_triple(_triple(right, "value", "90"))
    EntityResolver(similarity_fn=lambda _left, _right: 1.0).resolve(kg)
    assert left in kg.graph and right in kg.graph


def test_club_designator_is_resolved_without_semantic_similarity():
    kg = OnlineKG()
    kg.add_triple(_triple("Cerro Porteño", "country", "Paraguay"))
    kg.add_triple(_triple("Club Cerro Porteño", "founded", "1912"))
    semantic_calls = []

    def no_semantic_match(left, right):
        semantic_calls.append((left, right))
        return 0.0

    EntityResolver(similarity_fn=no_semantic_match).resolve(kg)

    assert "Cerro Porteño" not in kg.graph
    assert kg.get_neighbors("Cerro Porteño", "founded") == ["1912"]
    assert kg.get_neighbors("Club Cerro Porteño", "country") == ["Paraguay"]
    assert semantic_calls == []
    assert kg.resolution_log[-1]["tier"] == "structural"


def test_core_name_query_resolves_when_only_full_club_name_exists():
    kg = OnlineKG()
    kg.add_triple(_triple("Club Cerro Porteño", "country", "Paraguay"))
    EntityResolver(similarity_fn=lambda _left, _right: 0.0).resolve(kg)

    assert kg.get_neighbors("Cerro Porteño", "country") == ["Paraguay"]


def test_football_club_suffix_is_resolved_without_semantic_similarity():
    kg = OnlineKG()
    kg.add_triple(_triple("Rank 8", "club", "Liverpool"))
    kg.add_triple(_triple("Liverpool", "country", "England"))
    kg.add_triple(_triple("Liverpool F.C.", "founded", "1892"))

    EntityResolver(similarity_fn=lambda _left, _right: 0.0).resolve(kg)

    assert "Liverpool" not in kg.graph
    assert kg.get_neighbors("Liverpool", "founded") == ["1892"]
    assert kg.get_neighbors("Liverpool F.C.", "country") == ["England"]
    assert kg.resolution_log[-1]["tier"] == "structural"


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


def test_multigraph_provenance_does_not_duplicate_lookup_values():
    kg = OnlineKG()
    kg.add_triple(Triple("revenue", "2015", "45", Provenance("table", "deterministic")))
    kg.add_triple(Triple("revenue", "2015", "45", Provenance("table", "llm")))

    assert kg.graph.number_of_edges() == 2
    assert kg.get_neighbors("revenue", "2015") == ["45"]
    assert len(kg.get_evidence("revenue", "45", "2015")) == 2
