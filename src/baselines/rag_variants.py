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
    second_stage_k: int = 3
    max_context_chars: int = 24_000
    # ``None`` deliberately keeps every table row when constructing a KG.
    # This is independent of top_k, which ranks text/web retrieval.
    max_table_rows_for_kg: int | None = None
    max_output_tokens: int = 1024
    temperature: float = 0.0

    use_rule_text_triples: bool = True
    # OUEG component-ablation switches. Defaults define the full system;
    # each False value removes one answer-time signal.
    use_record_nodes: bool = True
    use_path_guidance: bool = True
    # Scores can order reader presentation, but lexical overlap is not proof.
    # Keep this off unless explicitly running the historical ablation.
    use_lexical_tiebreak: bool = False
    use_hyperlink_expansion: bool = True
    # When structural candidates tie, add a linked passage for each candidate
    # before synthesis. This expands evidence only; it never prunes the graph.
    use_collision_evidence_expansion: bool = True
    collision_passage_budget: int = 12
    # L2 may fetch candidate-linked passages that were absent from the first
    # retrieval, but only after the reader explicitly reports missing
    # evidence.  The per-candidate limit prevents a popular early candidate
    # from consuming the evidence budget of the others.
    use_focus_evidence_augmentation: bool = True
    focus_passage_budget_per_candidate: int = 2
    # Resolve L1 diagnostics against grounded table values before asking L2
    # for more text. This avoids treating Rank/Year cells as entities.
    use_diagnostic_focus_resolution: bool = True
    focus_query_fallback_budget: int = 2
    l2_existing_witness_budget: int = 2
    l2_max_edges_per_candidate: int = 16
    l2_max_contexts_per_candidate: int = 3
    l2_context_snippet_chars: int = 900
    # On a blank or explicitly uncertain first response, make one
    # non-destructive re-read with an auditable focus pointer.
    use_adaptive_verification: bool = True
    # L2 normally receives a small sufficient state capsule, not the L1
    # prompt. ``complete_re_read`` is retained solely as a diagnostic ablation.
    l2_evidence_mode: str = "delta_only"
    use_prompt_compression: bool = True
    # Keep the complete KG in the audit artifact, while presenting the answer
    # model with a bounded set of grounded paths and their evidence.
    use_path_focused_prompt: bool = True
    prompt_path_budget: int = 8
    # OUEG-only: prompt keeps the ambiguity visible by default. The two other
    # modes are explicit selective-prediction behaviours.
    ambiguity_policy: str = "prompt"
    oueg_context_mode: str = "lossless"

    def validate(self) -> None:
        if self.top_k < 1:
            raise ValueError("top_k must be positive")
        if self.second_stage_k < 0:
            raise ValueError("second_stage_k must be non-negative")
        if self.max_table_rows_for_kg is not None and self.max_table_rows_for_kg < 1:
            raise ValueError("max_table_rows_for_kg must be positive when set")
        if self.max_context_chars < 1 or self.max_output_tokens < 1:
            raise ValueError("context and output limits must be positive")
        if self.collision_passage_budget < 1:
            raise ValueError("collision_passage_budget must be positive")
        if self.focus_passage_budget_per_candidate < 1:
            raise ValueError("focus_passage_budget_per_candidate must be positive")
        for name in (
            "focus_query_fallback_budget", "l2_existing_witness_budget",
            "l2_max_edges_per_candidate", "l2_max_contexts_per_candidate",
            "l2_context_snippet_chars",
        ):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")
        if not isinstance(self.use_rule_text_triples, bool):
            raise ValueError("use_rule_text_triples must be boolean")
        for name in (
            "use_record_nodes", "use_path_guidance", "use_lexical_tiebreak",
            "use_hyperlink_expansion", "use_collision_evidence_expansion",
            "use_focus_evidence_augmentation",
            "use_diagnostic_focus_resolution",
            "use_adaptive_verification", "use_prompt_compression",
            "use_path_focused_prompt",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be boolean")
        if self.prompt_path_budget < 1:
            raise ValueError("prompt_path_budget must be positive")
        if self.ambiguity_policy not in {"prompt", "return_candidates", "lexical_tiebreak"}:
            raise ValueError("ambiguity_policy must be prompt, return_candidates, or lexical_tiebreak")
        if self.l2_evidence_mode not in {"delta_only", "complete_re_read"}:
            raise ValueError("l2_evidence_mode must be delta_only or complete_re_read")
        if self.oueg_context_mode not in {"lossless", "extractive"}:
            raise ValueError("oueg_context_mode must be lossless or extractive")


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
