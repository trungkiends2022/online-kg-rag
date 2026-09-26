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


def _row_text(table_name: str, row: dict) -> str:
    cells = " ".join(f"{column} {value}" for column, value in row.items())
    return f"{table_name} {cells}"


def _select_table_rows(
    question: str,
    table_groups: list[dict],
    *,
    top_k: int,
    anchor,
) -> list[dict]:
    """Select a bounded union of anchored and lexically relevant table rows."""
    candidates = []
    for table_index, group in enumerate(table_groups):
        table_name = str(group.get("table_name", f"table_{table_index}"))
        for row_index, row in enumerate(group.get("rows", [])):
            candidates.append({
                "table_index": table_index,
                "row_index": row_index,
                "row": row,
                "text": _row_text(table_name, row),
            })
    if len(candidates) <= top_k:
        selected = candidates
    else:
        corpus = [_tokenize(item["text"]) for item in candidates]
        scores = BM25Okapi(corpus).get_scores(_tokenize(question))
        ranked = sorted(
            zip(candidates, scores),
            key=lambda item: (-item[1], item[0]["table_index"], item[0]["row_index"]),
        )
        required_values = {
            normalize_key(value)
            for value in anchor.bridge_entities
            if str(value).strip()
        }
        for constraint in anchor.table_constraints:
            required_values.update(
                normalize_key(value) for value in constraint.get("candidates", ())
                if str(value).strip()
            )
        anchored, remaining = [], []
        for item, score in ranked:
            row_values = {normalize_key(value) for value in item["row"].values()}
            (anchored if required_values & row_values else remaining).append((item, score))
        selected = [item for item, _ in (anchored + remaining)[:top_k]]

    by_table: dict[int, list[dict]] = {}
    for item in selected:
        by_table.setdefault(item["table_index"], []).append(item)
    output = []
    for table_index, items in sorted(by_table.items()):
        original = table_groups[table_index]
        ordered = sorted(items, key=lambda item: item["row_index"])
        group = {
            key: value for key, value in original.items()
            if key not in {"rows", "row_indices"}
        }
        group["rows"] = [item["row"] for item in ordered]
        group["row_indices"] = [item["row_index"] for item in ordered]
        output.append(group)
    return output


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


def _constraint_topk(
    entities: list[str], items: list[dict], question: str, top_k: int,
) -> list[dict]:
    """Rank one linked passage per table-derived candidate by the full question.

    This avoids spending the whole stage-two budget on candidates merely because
    they appear first in a table.  It remains deterministic and does not add an
    LLM call.
    """
    candidates: list[dict] = []
    seen: set[str] = set()
    for entity in entities:
        for item in _entity_topk(entity, items, top_k=1):
            item_id = _item_id(item)
            if item_id not in seen:
                candidates.append(item)
                seen.add(item_id)
    return _bm25_topk(question, candidates, "text", top_k)


def two_stage_retrieve(
    question: str,
    table_rows: list[dict],
    text_passages: list[dict],
    web_snippets: list[dict],
    top_k: int = 10,
    second_stage_k: int = 3,
) -> dict:
    """Add a bounded schema-aware stage to ordinary question BM25 retrieval."""
    anchor = anchor_question(question, table_rows)
    first = coarse_retrieve(
        question, table_rows, text_passages, web_snippets, top_k=top_k
    )
    first["table_rows"] = _select_table_rows(
        question, table_rows, top_k=top_k, anchor=anchor,
    )
    expansions = _query_expansions(question, table_rows)
    entity_queries = list(anchor.bridge_entities)
    table_constraints = list(anchor.table_constraints)
    constrained_candidates = list(dict.fromkeys(
        entity for constraint in table_constraints for entity in constraint["candidates"]
    ))

    def supplement(items: list[dict], selected: list[dict]) -> list[dict]:
        selected_ids = {_item_id(item) for item in selected}
        remaining = [item for item in items if _item_id(item) not in selected_ids]
        positions = {_item_id(item): index for index, item in enumerate(items)}
        added: list[dict] = []
        # A table can identify an entity that is absent from the question.  For
        # example, HybridQA's Walter Payton item requires rank=2 -> Walter
        # Payton (table) -> Walter Payton passage -> middle name.  Prioritise
        # these bridge-entity queries over generic header/schema expansions.
        if constrained_candidates and second_stage_k > 0:
            for item in _constraint_topk(
                constrained_candidates, remaining, question, second_stage_k
            ):
                item_id = _item_id(item)
                if item_id in selected_ids:
                    continue
                enriched = dict(item)
                position = positions[item_id]
                enriched["context_before"] = " ".join(
                    str(previous.get("text", ""))
                    for previous in items[max(0, position - 2):position]
                )
                added.append(enriched)
                selected_ids.add(item_id)
                if len(added) >= second_stage_k:
                    return selected + added
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
            "selected_table_rows": sum(
                len(group.get("rows", [])) for group in first["table_rows"]
            ),
            "stage2_budget": second_stage_k,
            "expansion_queries": expansions,
            "entity_anchor": anchor.to_dict(),
            "entity_queries": entity_queries,
            "table_constraints": table_constraints,
            "constraint_policy": {
                "allowed_output_values": list(dict.fromkeys(
                    entity for constraint in table_constraints
                    if constraint.get("enforce_output")
                    for entity in constraint["candidates"]
                )),
                "require_table_evidence": bool(table_constraints),
            },
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
