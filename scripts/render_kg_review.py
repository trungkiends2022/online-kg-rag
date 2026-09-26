#!/usr/bin/env python3
"""Render an auditable OnlineKG trace as full and focused SVG review diagrams."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


TEXT_COLOR = "#D97706"
TABLE_COLOR = "#2563EB"
HIGHLIGHT_COLOR = "#15803D"
ANCHOR_FILL = "#FEF3C7"
ENTITY_FILL = "#EFF6FF"
VALUE_FILL = "#DCFCE7"


def dot_escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def short(value: object, width: int = 44) -> str:
    text = str(value)
    if len(text) <= width:
        return text
    return text[: width - 1].rstrip() + "…"


def node_id(index: int) -> str:
    return f"n{index}"


def render(trace: dict, *, focused: bool) -> str:
    edges = list(trace["edges"])
    anchors = {
        "Dazu Rock Carvings", "Dazu District", "Dazu County",
        "Shuangqiao District", "Dazu County and Shuangqiao District",
        "new Dazu District", "7th century AD",
    }
    if focused:
        edges = [
            edge for edge in edges
            if edge["head"] in anchors or edge["tail"] in anchors
        ]
    nodes = list(dict.fromkeys(
        [node for edge in edges for node in (edge["head"], edge["tail"])]
    ))
    ids = {node: node_id(index) for index, node in enumerate(nodes)}
    heads = {edge["head"] for edge in edges}
    summary = trace.get("summary", {})
    title = "Focused evidence KG" if focused else "Full semantic Online KG"
    label = (
        f"{title} — HybridQA 90f313b8d9f4c145\\n"
        f"{len(nodes)} nodes · {len(edges)} semantic edges · "
        f"text context on {summary.get('num_contextualized_edges', 0)} full-KG edges"
    )
    if focused:
        label += (
            "\\nGreen edge = answer fact. Dashed clusters expose the current "
            "unresolved gap between 'new Dazu District' and 'Dazu District'."
        )
    lines = [
        "digraph OnlineKG {",
        '  graph [rankdir=LR, bgcolor="white", pad="0.3", nodesep="0.35", ranksep="1.1",',
        f'         label="{dot_escape(label)}", labelloc=t, fontsize=18, fontname="Helvetica Bold",',
        '         concentrate=false, splines=spline];',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=10, color="#64748B"];',
        '  edge [fontname="Helvetica", fontsize=8, arrowsize=0.7];',
    ]
    if focused:
        lines.extend([
            '  subgraph cluster_site { label="Site and dating evidence"; color="#F59E0B"; style="rounded,dashed";',
            f'    {ids.get("Dazu Rock Carvings", "")}; {ids.get("7th century AD", "")}; {ids.get("Dazu District", "")};',
            '  }',
            '  subgraph cluster_admin { label="Merged-county evidence (separate component)"; color="#A855F7"; style="rounded,dashed";',
            f'    {ids.get("Dazu County", "")}; {ids.get("Shuangqiao District", "")}; {ids.get("Dazu County and Shuangqiao District", "")}; {ids.get("new Dazu District", "")};',
            '  }',
        ])
    for name in nodes:
        is_value = name not in heads
        fill = ANCHOR_FILL if name in anchors else (VALUE_FILL if is_value else ENTITY_FILL)
        shape = "ellipse" if is_value else "box"
        lines.append(
            f'  {ids[name]} [label="{dot_escape(short(name))}", shape={shape}, fillcolor="{fill}", '
            f'tooltip="{dot_escape(name)}"];'
        )
    for edge in edges:
        provenance = edge.get("provenance") or {}
        source_type = provenance.get("source_type", "unknown")
        color = TABLE_COLOR if source_type == "table" else TEXT_COLOR
        is_answer = (
            edge["head"] == "Dazu Rock Carvings"
            and edge["relation"] == "date_back_to"
            and edge["tail"] == "7th century AD"
        )
        if is_answer:
            color = HIGHLIGHT_COLOR
        source_id = provenance.get("source_id", "unknown")
        context = " ".join(item.get("text", "") for item in edge.get("contexts", []))
        tooltip = f"{source_type}: {source_id}\\n{context}".strip()
        edge_label = f'{edge["relation"]}\\n[{source_type.upper()}]'
        style = 'penwidth=3.0' if is_answer else 'penwidth=1.2'
        lines.append(
            f'  {ids[edge["head"]]} -> {ids[edge["tail"]]} '
            f'[label="{dot_escape(edge_label)}", color="{color}", fontcolor="{color}", '
            f'{style}, tooltip="{dot_escape(tooltip)}"];'
        )
    lines.extend([
        '  legend [shape=plain, label=<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="5">',
        '    <TR><TD COLSPAN="2"><B>Legend</B></TD></TR>',
        f'    <TR><TD><FONT COLOR="{TEXT_COLOR}">orange edge</FONT></TD><TD>LLM triple from retrieved text</TD></TR>',
        f'    <TR><TD><FONT COLOR="{TABLE_COLOR}">blue edge</FONT></TD><TD>deterministic table triple</TD></TR>',
        f'    <TR><TD><FONT COLOR="{HIGHLIGHT_COLOR}">green edge</FONT></TD><TD>answer fact</TD></TR>',
        '    <TR><TD BGCOLOR="#FEF3C7">yellow node</TD><TD>question-review anchor</TD></TR>',
        '  </TABLE>>];',
        "}",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path, help="JSON trace containing full_kg")
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    record = json.loads(args.trace.read_text(encoding="utf-8"))
    trace = record.get("full_kg", record)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, focused in (("full", False), ("focus", True)):
        dot_path = args.output_dir / f"hybridqa_groq_gpt_oss_kg_{name}.dot"
        svg_path = dot_path.with_suffix(".svg")
        dot_path.write_text(render(trace, focused=focused), encoding="utf-8")
        subprocess.run(["dot", "-Tsvg", str(dot_path), "-o", str(svg_path)], check=True)
        print(svg_path)


if __name__ == "__main__":
    main()
