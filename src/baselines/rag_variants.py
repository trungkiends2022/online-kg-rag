"""Controlled non-KG RAG baselines for HybridQA and FinQA."""

from __future__ import annotations

import time
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from src.datasets.schema import DatasetExample
from src.llm.client import get_provider, llm_call


@dataclass(frozen=True)
class RAGConfig:
    top_k: int = 5
    max_context_chars: int = 24_000
    max_output_tokens: int = 1024
    temperature: float = 0.0

    def validate(self) -> None:
        if self.top_k < 1:
            raise ValueError("top_k must be positive")
        if self.max_context_chars < 1 or self.max_output_tokens < 1:
            raise ValueError("context and output limits must be positive")


def flatten_documents(example: DatasetExample) -> list[dict]:
    """Turn table rows and passages into comparable text retrieval units."""
    documents = []
    for table_index, group in enumerate(example.table_rows):
        table_name = group.get("table_name", f"table_{table_index}")
        for row_index, row in enumerate(group.get("rows", [])):
            values = ". ".join(f"{column} is {value}" for column, value in row.items())
            documents.append({
                "id": f"table:{table_name}:row:{row_index}",
                "source_type": "table",
                "text": f"Table {table_name}. {values}.",
            })
    for passage in example.text_passages:
        documents.append({
            "id": f'text:{passage["id"]}',
            "source_type": "text",
            "text": passage["text"],
        })
    for index, snippet in enumerate(example.web_snippets):
        source_id = snippet.get("url", str(index))
        documents.append({
            "id": f"web:{source_id}",
            "source_type": "web",
            "text": snippet["text"],
        })
    return documents


def rank_documents(query: str, documents: list[dict], top_k: int) -> list[dict]:
    if not documents:
        return []
    tokenize = lambda text: str(text).lower().split()
    model = BM25Okapi([tokenize(document["text"]) for document in documents])
    scores = model.get_scores(tokenize(query))
    ranked = sorted(
        enumerate(zip(documents, scores)),
        key=lambda item: (-item[1][1], item[0]),
    )
    return [document for _, (document, _) in ranked[:top_k]]


def _bounded_context(documents: list[dict], limit: int) -> tuple[str, list[str]]:
    blocks, ids, used = [], [], 0
    for document in documents:
        block = f'[{document["id"]}] {document["text"]}'
        if used + len(block) > limit:
            continue
        blocks.append(block)
        ids.append(document["id"])
        used += len(block)
    return "\n\n".join(blocks), ids


def _answer_prompt(question: str, context: str) -> str:
    return f"""Answer the question using only the evidence below.
Return only the shortest answer span or numeric answer. Do not explain.

Question: {question}

Evidence:
{context}

Answer:"""


class _RAGBaseline:
    method_name = "base"

    def __init__(self, config: RAGConfig | None = None):
        self.config = config or RAGConfig()
        self.config.validate()

    def _complete(
        self, prompt: str, *, llm_calls: int, metadata: dict, started: float | None = None
    ) -> dict:
        provider = get_provider()
        started = started if started is not None else time.perf_counter()
        answer = llm_call(
            prompt,
            max_tokens=self.config.max_output_tokens,
            temperature=self.config.temperature,
        ).strip()
        return {
            "answer": answer,
            "method": self.method_name,
            "provider": provider.name,
            "model": getattr(provider, "model", None),
            "llm_calls": llm_calls,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "temperature": self.config.temperature,
            **metadata,
        }


class FlatTableBM25Baseline(_RAGBaseline):
    """Flatten rows, mix them with passages, and retrieve once."""

    method_name = "flat_table_bm25"

    def run(self, example: DatasetExample) -> dict:
        selected = rank_documents(
            example.question, flatten_documents(example), self.config.top_k
        )
        context, ids = _bounded_context(selected, self.config.max_context_chars)
        prompt = _answer_prompt(example.question, context)
        return self._complete(prompt, llm_calls=1, metadata={
            "retrieved_document_ids": ids,
            "prompt_chars": len(prompt),
            "top_k": self.config.top_k,
        })


class OracleEvidenceBaseline(_RAGBaseline):
    """Answer from dataset-provided supporting evidence (retrieval upper bound)."""

    method_name = "oracle_evidence_llm"

    def _oracle_documents(self, example: DatasetExample) -> list[dict]:
        if example.metadata.get("dataset") == "finqa":
            evidence = example.metadata.get("gold_evidence") or {}
            return [
                {"id": f"gold:{key}", "source_type": "gold", "text": str(value)}
                for key, value in evidence.items()
            ]

        answer_nodes = example.metadata.get("answer_nodes") or []
        documents, seen = [], set()
        passage_by_id = {passage["id"]: passage for passage in example.text_passages}
        for index, node in enumerate(answer_nodes):
            if not isinstance(node, (list, tuple)) or len(node) < 2:
                continue
            position = node[1]
            if isinstance(position, (list, tuple)) and position:
                row_index = position[0]
                for group in example.table_rows:
                    rows = group.get("rows", [])
                    if isinstance(row_index, int) and 0 <= row_index < len(rows):
                        key = f'gold:table:{group.get("table_name", "table")}:{row_index}'
                        if key not in seen:
                            seen.add(key)
                            row = rows[row_index]
                            text = ". ".join(f"{k} is {v}" for k, v in row.items())
                            documents.append({"id": key, "source_type": "gold", "text": text})
            if len(node) >= 3 and node[2] in passage_by_id:
                passage = passage_by_id[node[2]]
                key = f'gold:text:{passage["id"]}'
                if key not in seen:
                    seen.add(key)
                    documents.append({"id": key, "source_type": "gold", "text": passage["text"]})
        return documents

    def run(self, example: DatasetExample) -> dict:
        documents = self._oracle_documents(example)
        if not documents:
            raise ValueError(
                "No oracle evidence annotation found. Use FinQA gold_inds or "
                "HybridQA *.traced.json with answer-node."
            )
        context, ids = _bounded_context(documents, self.config.max_context_chars)
        prompt = _answer_prompt(example.question, context)
        return self._complete(prompt, llm_calls=1, metadata={
            "oracle_document_ids": ids,
            "prompt_chars": len(prompt),
        })
