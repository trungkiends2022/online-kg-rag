"""Coarse retrieval: lọc top-k item liên quan nhất từ mỗi nguồn trước khi extract triples.
Tránh chạy Entity/Relation Extractor trên toàn bộ corpus (tốn LLM call).

Bản này dùng BM25 đơn giản trên text/web; table thường ít số dòng hơn nên giữ nguyên
hoặc lọc theo keyword match cột. Thay bằng dense retriever (embedding) khi cần độ chính
xác cao hơn.
"""

from __future__ import annotations

from rank_bm25 import BM25Okapi


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
