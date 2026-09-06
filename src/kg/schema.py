"""Cấu trúc dữ liệu dùng chung: Triple có provenance (nguồn gốc trace được)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Provenance:
    source_type: str          # "table" | "text" | "web"
    source_id: str             # table name / passage id / url
    raw_snippet: str = ""      # đoạn gốc sinh ra triple này (debug/trace)
    source_group: str | None = None
    domain: str | None = None


@dataclass(frozen=True)
class EvidenceRef:
    """Immutable KG edge evidence captured during sandbox execution."""

    head: str
    relation: str
    tail: str
    source_type: str
    source_id: str
    source_group: str | None = None
    domain: str | None = None


@dataclass
class Triple:
    head: str
    relation: str
    tail: str
    provenance: Provenance
