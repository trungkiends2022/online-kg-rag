"""ODYSSEY: question-guided, destructively pruned hybrid-graph baseline.

Implements the published ODYSSEY stages: three LLM question-analysis calls,
sub-table selection, a cell--document/entity graph, semantic seed matching,
three-hop BFS, hop-wise reader calls, then full-context fallback.  The original
paper uses spaCy-transformer NER and INSTRUCTOR-XL; portable regex/lexical
fallbacks are used here and are recorded in each result for auditability.
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Callable

from src.baselines.rag_variants import RAGConfig
from src.datasets.schema import DatasetExample
from src.llm.client import get_provider, llm_call


_STOP = {"a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does", "for", "from", "how", "in", "is", "it", "of", "on", "or", "the", "that", "this", "to", "was", "what", "when", "where", "which", "who", "whose", "with"}
_CAPITALIZED = re.compile(r"\b(?:[A-Z][\w.-]*)(?:\s+[A-Z][\w.-]*){0,5}\b")
_NUMBER = re.compile(r"(?<!\w)[+-]?\d[\d,.%]*(?!\w)")


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if str(value).strip()))


def _terms(value: object) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", str(value).casefold()) if token not in _STOP}


@dataclass(frozen=True)
class OdysseyConfig:
    max_hops: int = 3
    semantic_threshold: float = 0.8

    def validate(self) -> None:
        if not 1 <= self.max_hops <= 3:
            raise ValueError("ODYSSEY max_hops must be in [1, 3]")
        if not 0 < self.semantic_threshold <= 1:
            raise ValueError("ODYSSEY semantic_threshold must be in (0, 1]")


class OdysseyBaseline:
    """Faithful operational ODYSSEY baseline, intentionally not an OUEG variant."""

    method_name = "odyssey"

    def __init__(self, config: RAGConfig | None = None, odyssey_config: OdysseyConfig | None = None, *, entity_extractor: Callable[[str], list[str]] | None = None, semantic_matcher: Callable[[str, list[str]], list[tuple[str, float]]] | None = None):
        self.config = config or RAGConfig()
        self.config.validate()
        self.odyssey_config = odyssey_config or OdysseyConfig()
        self.odyssey_config.validate()
        self.entity_extractor = entity_extractor or self._regex_entities
        self.semantic_matcher = semantic_matcher or self._lexical_matches
        self.entity_extraction_mode = "custom" if entity_extractor else "regex_fallback"
        self.semantic_matching_mode = "custom" if semantic_matcher else "lexical_fallback"

    @staticmethod
    def _regex_entities(text: str) -> list[str]:
        return _unique([match.group(0).strip() for match in _CAPITALIZED.finditer(text)] + [match.group(0) for match in _NUMBER.finditer(text)])

    @staticmethod
    def _lexical_matches(query: str, candidates: list[str]) -> list[tuple[str, float]]:
        query_terms, query_numbers = _terms(query), set(_NUMBER.findall(query))
        scored = []
        for candidate in candidates:
            candidate_terms = _terms(candidate)
            if not candidate_terms:
                continue
            overlap = len(query_terms & candidate_terms) / max(len(query_terms), len(candidate_terms))
            sequence = SequenceMatcher(None, " ".join(sorted(query_terms)), " ".join(sorted(candidate_terms))).ratio()
            exact_number = bool(query_numbers & set(_NUMBER.findall(candidate)))
            scored.append((candidate, round(max(overlap, sequence, 1.0 if exact_number else 0.0), 4)))
        return sorted(scored, key=lambda item: (-item[1], item[0]))

    @staticmethod
    def _json(raw: str, expected: type) -> object | None:
        value = str(raw or "").strip()
        if value.startswith("```"):
            value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value).strip()
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, expected) else None
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}|\[.*\]", value, re.S)
            if not match:
                return None
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, expected) else None

    def _max_tokens(self) -> int:
        provider = get_provider()
        return max(self.config.max_output_tokens, 512) if "gpt-oss" in str(getattr(provider, "model", "")).casefold() else self.config.max_output_tokens

    @staticmethod
    def _headers_and_name(example: DatasetExample) -> tuple[list[str], str]:
        headers, names = [], []
        for index, group in enumerate(example.table_rows):
            names.append(str(group.get("table_name", f"table_{index}")))
            for row in group.get("rows", []):
                headers.extend(str(header) for header in row)
        return _unique(headers), "; ".join(_unique(names)) or "table"

    def _analysis(self, example: DatasetExample) -> dict:
        headers, table_name = self._headers_and_name(example)
        entities_raw = llm_call(f"""You are ODYSSEY question analysis. Extract entities, explicit values, relations, and answer-type cues needed for table--text QA. Return strict JSON only: {{\"entities\":[\"...\"]}}.\nQuestion: {example.question}\nTable name: {table_name}\nHeaders: {json.dumps(headers, ensure_ascii=False)}""", max_tokens=self._max_tokens(), temperature=self.config.temperature)
        parsed = self._json(entities_raw, dict) or {}
        entities = _unique([str(value) for value in parsed.get("entities", [])])
        if not entities:
            entities = _unique([match.group(0).strip() for match in _CAPITALIZED.finditer(example.question)] + _NUMBER.findall(example.question))
        headers_raw = llm_call(f"""You are ODYSSEY question analysis. Select headers required to find direct or bridge evidence. Return strict JSON only: {{\"headers\":[\"exact supplied header\"]}}.\nQuestion: {example.question}\nEntities: {json.dumps(entities, ensure_ascii=False)}\nHeaders: {json.dumps(headers, ensure_ascii=False)}""", max_tokens=self._max_tokens(), temperature=self.config.temperature)
        parsed = self._json(headers_raw, dict) or {}
        canonical = {header.casefold(): header for header in headers}
        selected = _unique([canonical[str(value).casefold()] for value in parsed.get("headers", []) if str(value).casefold() in canonical]) or headers
        mapping_raw = llm_call(f"""You are ODYSSEY question analysis. Map each entity to supplied relevant headers; use \"Others\" for passage-entity matching. Return strict JSON only: {{\"mapping\":{{\"entity\":[\"Header\" or \"Others\"]}}}}.\nQuestion: {example.question}\nEntities: {json.dumps(entities, ensure_ascii=False)}\nRelevant headers: {json.dumps(selected, ensure_ascii=False)}""", max_tokens=self._max_tokens(), temperature=self.config.temperature)
        parsed = self._json(mapping_raw, dict) or {}
        raw_mapping = parsed.get("mapping", {}) if isinstance(parsed.get("mapping", {}), dict) else {}
        mapping = {}
        for entity in entities:
            values = raw_mapping.get(entity, [])
            values = values if isinstance(values, list) else [values]
            mapping[entity] = _unique([str(value) for value in values if value == "Others" or value in selected]) or ["Others"]
        return {"entities": entities, "selected_headers": selected, "entity_header_mapping": mapping, "raw_responses": {"entities": entities_raw, "headers": headers_raw, "mapping": mapping_raw}}

    def _graph(self, example: DatasetExample, headers: list[str]) -> tuple[dict, dict]:
        nodes: dict[str, dict] = {}
        adjacency: dict[str, set[str]] = defaultdict(set)
        edges: dict[tuple[str, str], str] = {}
        link_cells: dict[str, list[str]] = defaultdict(list)

        def add_node(node_id: str, **metadata: object) -> None:
            nodes.setdefault(node_id, {"id": node_id, **metadata})

        def add_edge(left: str, right: str, kind: str) -> None:
            if left == right:
                return
            adjacency[left].add(right)
            adjacency[right].add(left)
            edges[tuple(sorted((left, right)))] = kind

        for table_i, group in enumerate(example.table_rows):
            rows = list(group.get("rows", []))
            indices = list(group.get("row_indices", []))
            indices = indices if len(rows) == len(indices) else list(range(len(rows)))
            links = defaultdict(list)
            for link in group.get("cell_links", []):
                links[(int(link.get("row_index", -1)), str(link.get("column_name", "")))].append(link)
            for row, row_i in zip(rows, indices):
                row_cells = []
                for header in headers:
                    if header not in row:
                        continue
                    value = str(row[header])
                    node_id = f"cell:{table_i}:{row_i}:{header}:{value}"
                    add_node(node_id, type="cell", table=str(group.get("table_name", f"table_{table_i}")), row_index=int(row_i), header=header, value=value)
                    row_cells.append(node_id)
                    for link in links[(int(row_i), header)]:
                        target = str(link.get("url") or link.get("passage_id") or "").strip().removeprefix("/wiki/").casefold()
                        if target:
                            link_cells[target].append(node_id)
                for index, left in enumerate(row_cells):
                    for right in row_cells[index + 1:]:
                        add_edge(left, right, "table_row")
        for passage in example.text_passages:
            source_id = str(passage.get("id", ""))
            if not source_id:
                continue
            doc_id = f"doc:{source_id}"
            text = " ".join(str(passage.get(field, "")) for field in ("context_before", "text")).strip()
            add_node(doc_id, type="document", source_id=source_id, text=text)
            for entity in self.entity_extractor(text):
                entity_id = f"entity:{entity.casefold()}"
                add_node(entity_id, type="entity", value=entity)
                add_edge(doc_id, entity_id, "document_entity")
            for cell_id in link_cells.get(source_id.casefold(), []) + link_cells.get(source_id.removeprefix("/wiki/").casefold(), []):
                add_edge(cell_id, doc_id, "cell_document")
        audit = {"node_count": len(nodes), "edge_count": len(edges), "cell_count": sum(node["type"] == "cell" for node in nodes.values()), "document_count": sum(node["type"] == "document" for node in nodes.values()), "entity_count": sum(node["type"] == "entity" for node in nodes.values())}
        return {"nodes": nodes, "adjacency": adjacency}, audit

    def _seeds(self, graph: dict, analysis: dict) -> tuple[list[str], list[dict]]:
        seeds, audit = [], []
        for entity, mapped_headers in analysis["entity_header_mapping"].items():
            candidates = [(node_id, str(node.get("value", ""))) for node_id, node in graph["nodes"].items() if (node["type"] == "entity" and "Others" in mapped_headers) or (node["type"] == "cell" and "Others" not in mapped_headers and node.get("header") in mapped_headers)]
            ranked = self.semantic_matcher(entity, [value for _, value in candidates])
            accepted = {value for value, score in ranked if score >= self.odyssey_config.semantic_threshold}
            matched = [node_id for node_id, value in candidates if value in accepted]
            retried_all_columns = False
            if not matched and "Others" not in mapped_headers:
                retried_all_columns = True
                candidates = [(node_id, str(node.get("value", ""))) for node_id, node in graph["nodes"].items() if node["type"] == "cell"]
                ranked = self.semantic_matcher(entity, [value for _, value in candidates])
                accepted = {value for value, score in ranked if score >= self.odyssey_config.semantic_threshold}
                matched = [node_id for node_id, value in candidates if value in accepted]
            seeds.extend(matched)
            audit.append({"entity": entity, "mapped_headers": mapped_headers, "matched_node_ids": matched, "fallback_all_columns": retried_all_columns, "top_matches": [{"value": value, "score": score} for value, score in ranked[:5]]})
        return _unique(seeds), audit

    def _hops(self, graph: dict, seeds: list[str]) -> list[set[str]]:
        visited, frontier, result = set(seeds), set(seeds), []
        for _ in range(self.odyssey_config.max_hops):
            frontier = {target for node_id in frontier for target in graph["adjacency"].get(node_id, set()) if target not in visited}
            result.append(frontier)
            visited.update(frontier)
            if not frontier:
                break
        return result

    def _context(self, graph: dict, included: set[str], example: DatasetExample) -> tuple[str, list[str]]:
        rows: dict[tuple[str, int], dict] = {}
        passage_ids = []
        for node_id in included:
            node = graph["nodes"][node_id]
            if node["type"] == "cell":
                rows.setdefault((node["table"], node["row_index"]), {})[node["header"]] = node["value"]
            elif node["type"] == "document":
                passage_ids.append(node["source_id"])
        payload = {"table_rows": [{"table": table, "row_index": row_i, "values": values} for (table, row_i), values in sorted(rows.items())], "passages": [{"id": passage_id, "text": next((str(item.get("text", "")) for item in example.text_passages if str(item.get("id")) == passage_id), "")} for passage_id in _unique(passage_ids)]}
        if len(json.dumps(payload, ensure_ascii=False)) <= self.config.max_context_chars:
            return json.dumps(payload, ensure_ascii=False), _unique(passage_ids)
        bounded = {"table_rows": [], "passages": []}
        for key in ("table_rows", "passages"):
            for item in payload[key]:
                candidate = {**bounded, key: [*bounded[key], item]}
                if len(json.dumps(candidate, ensure_ascii=False)) <= self.config.max_context_chars:
                    bounded[key].append(item)
        return json.dumps(bounded, ensure_ascii=False), [item["id"] for item in bounded["passages"]]

    @staticmethod
    def _reader_response(raw: str) -> tuple[str | None, list[str]]:
        match = re.search(r"final\s+answer\s*:\s*(.+)", str(raw), re.I)
        answer = match.group(1).splitlines()[0].strip() if match else str(raw).strip().splitlines()[0] if raw else ""
        if answer.casefold().strip(" .") in {"", "none", "unknown", "n/a", "na", "null"}:
            answer = None
        passages = re.search(r"relevant\s+passages\s*:\s*(\[[^\]]*\])", str(raw), re.I | re.S)
        if not passages:
            return answer, []
        try:
            parsed = json.loads(passages.group(1).replace("'", '"'))
            return answer, _unique([str(value) for value in parsed]) if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return answer, []

    def _reader_prompt(self, question: str, context: str, scope: str) -> str:
        return f"""You are an ODYSSEY Hybrid-QA reader. Answer using only {scope}.\nQuestion: {question}\nContext: {context}\nReturn exactly two lines:\nFinal Answer: <short answer, or None if insufficient>\nRelevant Passages: [<passage ids relevant for the next hop>]"""

    def run(self, example: DatasetExample) -> dict:
        started = time.perf_counter()
        analysis = self._analysis(example)
        graph, graph_audit = self._graph(example, analysis["selected_headers"])
        seeds, seed_audit = self._seeds(graph, analysis)
        hops = self._hops(graph, seeds)
        included, attempts, answer = set(seeds), [], None
        carried = []
        for hop, reached in enumerate(hops, 1):
            included.update(reached)
            included.update(node_id for node_id, node in graph["nodes"].items() if node["type"] == "document" and node.get("source_id") in carried)
            context, exposed = self._context(graph, included, example)
            raw = llm_call(self._reader_prompt(example.question, context, f"the ODYSSEY pruned graph through hop {hop}"), max_tokens=self._max_tokens(), temperature=self.config.temperature)
            answer, requested = self._reader_response(raw)
            carried = [passage for passage in requested if passage in exposed]
            attempts.append({"hop": hop, "fallback": False, "prompt_chars": len(context), "exposed_passage_ids": exposed, "requested_passage_ids": carried, "raw_response": raw, "answer": answer})
            if answer:
                break
        fallback = not bool(answer)
        if fallback:
            context, exposed = self._context(graph, set(graph["nodes"]), example)
            raw = llm_call(self._reader_prompt(example.question, context, "the full table-and-text fallback context"), max_tokens=self._max_tokens(), temperature=self.config.temperature)
            answer, _ = self._reader_response(raw)
            attempts.append({"hop": "full", "fallback": True, "prompt_chars": len(context), "exposed_passage_ids": exposed, "requested_passage_ids": [], "raw_response": raw, "answer": answer})
        provider = get_provider()
        return {"answer": answer, "method": self.method_name, "provider": provider.name, "model": getattr(provider, "model", None), "temperature": self.config.temperature, "latency_ms": round((time.perf_counter() - started) * 1000, 2), "execution_mode": "odyssey_hybrid_graph_hopwise", "odyssey_question_analysis": analysis, "odyssey_graph": graph_audit, "odyssey_seed_matches": seed_audit, "odyssey_seed_node_ids": seeds, "odyssey_hop_node_counts": [len(hop) for hop in hops], "odyssey_reader_attempts": attempts, "odyssey_full_context_fallback": fallback, "entity_extraction_mode": self.entity_extraction_mode, "semantic_matching_mode": self.semantic_matching_mode, "max_hops": self.odyssey_config.max_hops, "semantic_threshold": self.odyssey_config.semantic_threshold}
