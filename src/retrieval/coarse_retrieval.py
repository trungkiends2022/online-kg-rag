"""Coarse retrieval: lọc top-k item liên quan nhất từ mỗi nguồn trước khi extract triples.
Tránh chạy Entity/Relation Extractor trên toàn bộ corpus (tốn LLM call).

Bản này dùng BM25 đơn giản trên text/web; table thường ít số dòng hơn nên giữ nguyên
hoặc lọc theo keyword match cột. Thay bằng dense retriever (embedding) khi cần độ chính
xác cao hơn.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from src.kg.normalization import normalize_key
from src.planning.entity_anchor import anchor_question


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def _bm25_topk(query: str, items: list[dict], text_field: str, top_k: int) -> list[dict]:
    if not items:
        return []
    corpus = [_tokenize(it[text_field]) for it in items]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(zip(items, scores), key=lambda x: x[1], reverse=True)
    return [it for it, _ in ranked[:top_k]]


def _query_expansions(question: str, table_rows: list[dict]) -> list[str]:
    """Build deterministic relation/schema queries without an LLM call."""
    lowered = question.lower()
    expansions: list[str] = []
    if "interest" in lowered:
        expansions.append("interest amount expense payable annually per year")
    if any(term in lowered for term in ("percentage", "percent", "ratio")):
        expansions.append("percentage ratio total amount")
    if re.search(r"\b(?:19|20)\d{2}\b", lowered):
        expansions.append("annual annually year period from to")

    headers: list[str] = []
    seen_headers: set[str] = set()
    for table in table_rows:
        for row in table.get("rows", []):
            for header in row:
                header_text = str(header).strip()
                key = header_text.lower()
                if header_text and key not in seen_headers:
                    headers.append(header_text)
                    seen_headers.add(key)
                if len(headers) >= 20:
                    break
            if len(headers) >= 20:
                break
        if len(headers) >= 20:
            break
    if headers:
        expansions.append(" ".join(headers))
    return expansions


def _item_id(item: dict) -> str:
    return str(item.get("id") or item.get("url") or item.get("text", ""))


def _entity_topk(entity: str, items: list[dict], top_k: int) -> list[dict]:
    """Rank exact entity mentions ahead of BM25 ties and short documents."""
    entity_tokens = set(normalize_key(entity).split())
    direct = [
        item for item in items
        if entity_tokens and entity_tokens.issubset(set(normalize_key(item.get("text", "")).split()))
    ]
    direct_ids = {_item_id(item) for item in direct}
    fallback = _bm25_topk(entity, [item for item in items if _item_id(item) not in direct_ids], "text", top_k)
    return (direct + fallback)[:top_k]


def two_stage_retrieve(
    question: str,
    table_rows: list[dict],
    text_passages: list[dict],
    web_snippets: list[dict],
    top_k: int = 10,
    second_stage_k: int = 3,
) -> dict:
    """Add a bounded schema-aware stage to ordinary question BM25 retrieval."""
    first = coarse_retrieve(
        question, table_rows, text_passages, web_snippets, top_k=top_k
    )
    expansions = _query_expansions(question, table_rows)
    anchor = anchor_question(question, table_rows)
    entity_queries = list(anchor.bridge_entities)

    def supplement(items: list[dict], selected: list[dict]) -> list[dict]:
        selected_ids = {_item_id(item) for item in selected}
        remaining = [item for item in items if _item_id(item) not in selected_ids]
        positions = {_item_id(item): index for index, item in enumerate(items)}
        added: list[dict] = []
        # A table can identify an entity that is absent from the question.  For
        # example, HybridQA's Walter Payton item requires rank=2 -> Walter
        # Payton (table) -> Walter Payton passage -> middle name.  Prioritise
        # these bridge-entity queries over generic header/schema expansions.
        for query in entity_queries + expansions:
            ranked = (
                _entity_topk(query, remaining, second_stage_k)
                if query in entity_queries
                else _bm25_topk(query, remaining, "text", second_stage_k)
            )
            for item in ranked:
                item_id = _item_id(item)
                if item_id not in selected_ids:
                    enriched = dict(item)
                    position = positions[item_id]
                    # Adjacent prose commonly carries the antecedent (e.g.
                    # "2025 notes") for a following numerical sentence. Supply
                    # it as resolution-only context without another API call.
                    enriched["context_before"] = " ".join(
                        str(previous.get("text", ""))
                        for previous in items[max(0, position - 2):position]
                    )
                    added.append(enriched)
                    selected_ids.add(item_id)
                if len(added) >= second_stage_k:
                    return selected + added
        return selected + added

    return {
        "table_rows": first["table_rows"],
        "text_passages": supplement(text_passages, first["text_passages"]),
        "web_snippets": supplement(web_snippets, first["web_snippets"]),
        "retrieval_trace": {
            "strategy": "two_stage_bm25_schema",
            "stage1_top_k": top_k,
            "stage2_budget": second_stage_k,
            "expansion_queries": expansions,
            "entity_anchor": anchor.to_dict(),
            "entity_queries": entity_queries,
        },
    }


def coarse_retrieve(
    question: str,
    table_rows: list[dict],
    text_passages: list[dict],
    web_snippets: list[dict],
    top_k: int = 10,
) -> dict:
    return {
        "table_rows": table_rows[:top_k],  # table thường đã được filter trước ở nguồn
        "text_passages": _bm25_topk(question, text_passages, "text", top_k),
        "web_snippets": _bm25_topk(question, web_snippets, "text", top_k),
    }
