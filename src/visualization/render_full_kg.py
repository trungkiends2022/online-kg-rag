"""Render a pipeline ``full_kg`` JSONL trace as a Graphviz diagram."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


TABLE_COLOR = "#2563EB"
TEXT_COLOR = "#D97706"
VALUE_FILL = "#DCFCE7"
ENTITY_FILL = "#EFF6FF"
ALIAS_FILL = "#F3E8FF"


def _dot(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _node_id(index: int) -> str:
    return f"n{index}"


def render(record: dict) -> str:
    trace = record["full_kg"]
    nodes = list(trace["nodes"])
    node_ids = {name: _node_id(i) for i, name in enumerate(nodes)}
    heads = {edge["head"] for edge in trace["edges"]}

    lines = [
        "digraph OnlineKG {",
        '  graph [rankdir=LR, bgcolor="white", pad="0.25", nodesep="0.35", ranksep="1.25",',
        '         label="Full Online KG — FinQA DVN/2014/page_85.pdf-1\\n23 nodes · 21 directed multi-edges · answer = 44.8",',
        '         labelloc=t, fontsize=20, fontname="Helvetica Bold"];',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#64748B"];',
        '  edge [fontname="Helvetica", fontsize=8, arrowsize=0.7];',
    ]

    for name in nodes:
        is_value = name not in heads
        fill = VALUE_FILL if is_value else ENTITY_FILL
        shape = "ellipse" if is_value else "box"
        lines.append(
            f'  {node_ids[name]} [label="{_dot(name)}", shape={shape}, fillcolor="{fill}"];'
        )

    for edge in trace["edges"]:
        provenance = edge.get("provenance") or {}
        source_type = provenance.get("source_type", "unknown")
        color = TABLE_COLOR if source_type == "table" else TEXT_COLOR
        source_id = provenance.get("source_id", "unknown")
        row_index = provenance.get("row_index")
        column = provenance.get("column_name")
        detail = f"row {row_index}" if row_index is not None else source_id
        if column:
            detail += f" · {column}"
        label = f'{edge["relation"]}\n[{source_type.upper()} · {detail}]'
        lines.append(
            f'  {node_ids[edge["head"]]} -> {node_ids[edge["tail"]]} '
            f'[label="{_dot(label)}", color="{color}", fontcolor="{color}", tooltip="{_dot(source_id)}"];'
        )

    for alias_index, (alias, canonical) in enumerate(trace.get("aliases", {}).items()):
        alias_id = f"alias{alias_index}"
        lines.append(
            f'  {alias_id} [label="{_dot(alias)}", shape=note, style="dashed,filled", '
            f'fillcolor="{ALIAS_FILL}", color="#7C3AED"];'
        )
        lines.append(
            f'  {alias_id} -> {node_ids[canonical]} [label="alias → canonical\n[LEXICAL · score 1.0]", '
            'style=dashed, color="#7C3AED", fontcolor="#7C3AED"];'
        )

    lines.extend(
        [
            '  legend [shape=plain, label=<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5">',
            '    <TR><TD COLSPAN="2"><B>Legend</B></TD></TR>',
            f'    <TR><TD><FONT COLOR="{TABLE_COLOR}">blue edge</FONT></TD><TD>table provenance</TD></TR>',
            f'    <TR><TD><FONT COLOR="{TEXT_COLOR}">orange edge</FONT></TD><TD>text provenance</TD></TR>',
            '    <TR><TD BGCOLOR="#DCFCE7">ellipse</TD><TD>value/literal</TD></TR>',
            '    <TR><TD BGCOLOR="#EFF6FF">box</TD><TD>entity/concept</TD></TR>',
            '    <TR><TD BGCOLOR="#F3E8FF">dashed note</TD><TD>alias (not a canonical KG node)</TD></TR>',
            '  </TABLE>>];',
            "}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Pipeline JSONL containing full_kg")
    parser.add_argument("output", type=Path, help="Output .dot file")
    args = parser.parse_args()
    first_line = next(line for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip())
    record = json.loads(first_line)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(record), encoding="utf-8")


if __name__ == "__main__":
    main()
