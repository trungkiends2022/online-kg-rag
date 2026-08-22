"""Cấu trúc dữ liệu dùng chung: Triple có provenance (nguồn gốc trace được)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Provenance:
    source_type: str          # "table" | "text" | "web"
    source_id: str             # table name / passage id / url
    raw_snippet: str = ""      # đoạn gốc sinh ra triple này (debug/trace)


@dataclass
class Triple:
    head: str
    relation: str
    tail: str
    provenance: Provenance
