"""Deterministic three-tier normalization for relations and KG entities."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from src.kg.online_kg import OnlineKG


RELATION_ALIASES = {
    "has_nationality": "nationality",
    "country_of_citizenship": "nationality",
    "date_of_birth": "birth_date",
    "birthdate": "birth_date",
    "born_on": "birth_date",
    "current_profession": "current_occupation",
    "former_profession": "former_occupation",
    "head_coach_in": "coached_in",
    "manages_from": "tenure_start",
    "managed_from": "tenure_start",
    "started": "tenure_start",
    "from": "tenure_start",
    "manages_to": "tenure_end",
    "managed_to": "tenure_end",
    "managed_until": "tenure_end",
    "ended": "tenure_end",
    "to": "tenure_end",
}

CANONICAL_RELATIONS = {
    "nationality", "birth_date", "current_occupation", "former_occupation",
    "coached_in", "tenure_start", "tenure_end", "occupation", "name",
}

DEFAULT_ENTITY_ALIASES = {
    "bac ho": "Hồ Chí Minh",
    "ho chi minh": "Hồ Chí Minh",
    "moroccan": "Morocco",
    "u s": "United States",
    "u s a": "United States",
    "usa": "United States",
    "united states of america": "United States",
}


def normalize_key(value: str) -> str:
    """Tier 1: Unicode fold, case fold, punctuation and whitespace cleanup."""
    decomposed = unicodedata.normalize("NFKD", str(value).strip())
    ascii_folded = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^\w]+", " ", ascii_folded.casefold()).strip()


def normalize_relation(value: str, *, fuzzy_threshold: float = 0.9) -> str:
    """Apply syntax normalization, ontology aliases, then conservative fuzzy match."""
    camel_split = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(value).strip())
    key = re.sub(r"[^a-zA-Z0-9]+", "_", camel_split).strip("_").lower()
    canonical = RELATION_ALIASES.get(key, key)
    if canonical in CANONICAL_RELATIONS:
        return canonical
    # Tier 3: repair small spelling variants only; semantic aliases remain explicit.
    match, score = max(
        ((candidate, SequenceMatcher(None, canonical, candidate).ratio())
         for candidate in CANONICAL_RELATIONS),
        key=lambda item: item[1],
    )
    return match if score >= fuzzy_threshold else canonical


SimilarityFn = Callable[[str, str], float]


class EntityResolver:
    """Resolve entities in three auditable tiers.

    ``similarity_fn`` can be an embedding cosine-similarity function. Without one,
    a conservative string similarity fallback is used and remains dependency-free.
    """

    def __init__(
        self,
        aliases: dict[str, str] | None = None,
        similarity_fn: SimilarityFn | None = None,
        semantic_threshold: float = 0.93,
    ):
        combined = dict(DEFAULT_ENTITY_ALIASES)
        if aliases:
            combined.update({normalize_key(k): v for k, v in aliases.items()})
        self.aliases = combined
        self.similarity_fn = similarity_fn or self._lexical_similarity
        self.semantic_threshold = semantic_threshold

    @staticmethod
    def _lexical_similarity(left: str, right: str) -> float:
        return SequenceMatcher(None, normalize_key(left), normalize_key(right)).ratio()

    @staticmethod
    def _display_score(value: str) -> tuple[int, int, int]:
        return (sum(ord(ch) > 127 for ch in value), len(value), sum(ch.isupper() for ch in value))

    @staticmethod
    def _is_literal(value: str) -> bool:
        key = normalize_key(value)
        return bool(re.fullmatch(r"[\d\s:./-]+", value.strip())) or bool(
            re.search(r"\b(?:january|february|march|april|may|june|july|august|"
                      r"september|october|november|december)\b", key)
        )

    @staticmethod
    def _role(kg: "OnlineKG", node: str) -> tuple[bool, bool]:
        has_outgoing = next(iter(kg.graph.out_edges(node)), None) is not None
        has_incoming = next(iter(kg.graph.in_edges(node)), None) is not None
        return (has_outgoing, has_incoming)

    def resolve(self, kg: "OnlineKG") -> None:
        # Tier 1: exact match after normalization.
        buckets: dict[str, list[str]] = defaultdict(list)
        for node in list(kg.graph.nodes()):
            buckets[normalize_key(node)].append(node)
        for group in buckets.values():
            if len(group) > 1:
                canonical = max(group, key=self._display_score)
                kg.merge_entities(canonical, [n for n in group if n != canonical], tier="lexical", score=1.0)

        # Tier 2: explicit domain aliases / ontology.
        for node in list(kg.graph.nodes()):
            canonical = self.aliases.get(normalize_key(node))
            if canonical and node != canonical:
                kg.merge_entities(canonical, [node], tier="alias", score=1.0)

        # Tier 3: optional embedding similarity (or conservative fallback).
        nodes = list(kg.graph.nodes())
        consumed: set[str] = set()
        for index, left in enumerate(nodes):
            if left in consumed or left not in kg.graph or self._is_literal(left):
                continue
            for right in nodes[index + 1:]:
                if right in consumed or right not in kg.graph or self._is_literal(right):
                    continue
                if self._role(kg, left) != self._role(kg, right):
                    continue
                score = float(self.similarity_fn(left, right))
                if score < self.semantic_threshold:
                    continue
                canonical = max((left, right), key=self._display_score)
                alias = right if canonical == left else left
                kg.merge_entities(canonical, [alias], tier="semantic", score=score)
                consumed.add(alias)

        # Resolve future query spellings too, not only aliases present during build.
        kg.entity_key_aliases = {
            normalize_key(node): node for node in kg.graph.nodes()
        }
        for alias_key, canonical in self.aliases.items():
            resolved = kg._resolve_entity(canonical)
            if resolved in kg.graph:
                kg.entity_key_aliases[alias_key] = resolved
