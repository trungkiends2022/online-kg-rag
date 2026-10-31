"""Deterministic local table operator execution for HybridQA and table-text QA.

Executes symbolic operations (interval filtering, extremum/argmax/argmin,
frequency/counting, latest/earliest selection, and cross-modal text condition matching)
locally in Python at zero token cost, producing TableWitness objects that act as hard
seeds for retrieval and grounded path generation.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TableWitness:
    """Symbolic witness identified by local table operations."""

    row_indices: tuple[int, ...]
    operator: str
    evidence_columns: tuple[str, ...]
    bridge_entities: tuple[str, ...]
    intermediate_values: dict[str, Any]
    hyperlinks: tuple[str, ...]
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def clean_number(val: Any) -> float | None:
    """Robustly extract a float from noisy table cells (currency, footnotes, commas)."""
    if val is None:
        return None
    val_clean = re.sub(r"\[.*?\]", "", str(val))
    val_clean = re.sub(r"[\$,€£%]", "", val_clean).strip()
    match = re.search(r"[-+]?\d+(?:,\d+)*(?:\.\d+)?", val_clean)
    if not match:
        return None
    num_str = match.group(0).replace(",", "")
    try:
        return float(num_str)
    except ValueError:
        return None


def is_summary_row(row: dict[str, Any]) -> bool:
    """Detect non-data summary rows like Total, Average, Summary."""
    for value in row.values():
        val = str(value).strip().lower()
        if val in ("total", "totals", "all", "overall", "average", "summary"):
            return True
    return False


def row_primary_entity(row: dict[str, Any]) -> str | None:
    """Pick the primary named entity representing this row."""
    preferred = (
        "team", "club", "artist", "player", "person", "name",
        "athlete", "driver", "title", "country", "city", "state", "school",
    )
    for pref in preferred:
        for key, val in row.items():
            if pref in key.lower() and str(val).strip():
                return str(val).strip()
    for key, val in row.items():
        if "rank" not in key.lower() and clean_number(val) is None and str(val).strip():
            return str(val).strip()
    return next((str(v).strip() for v in row.values() if str(v).strip()), None)


class TableOperatorPlanner:
    """Executes deterministic symbolic operators over table rows and linked passages."""

    def plan_numeric_interval(
        self, question: str, table_group: dict[str, Any]
    ) -> list[TableWitness]:
        """Operator 1: numeric_interval (e.g. 88.5 < revenue < 101.8)."""
        patterns = [
            (
                r"(?:less than|under|below|<)\s*(\d+(?:\.\d+)?)\s*(?:but|and)\s*(?:more than|greater than|over|>)\s*(\d+(?:\.\d+)?)",
                "upper_lower",
            ),
            (
                r"(?:more than|greater than|over|>)\s*(\d+(?:\.\d+)?)\s*(?:but|and)\s*(?:less than|under|below|<)\s*(\d+(?:\.\d+)?)",
                "lower_upper",
            ),
            (
                r"\bbetween\s*(\d+(?:\.\d+)?)\s*(?:and|to)\s*(\d+(?:\.\d+)?)",
                "lower_upper",
            ),
            (
                r"\bfrom\s*(\d+(?:\.\d+)?)\s*(?:to)\s*(\d+(?:\.\d+)?)",
                "lower_upper",
            ),
        ]
        lower, upper = None, None
        for pattern, order in patterns:
            match = re.search(pattern, question, re.I)
            if match:
                v1, v2 = float(match.group(1)), float(match.group(2))
                lower, upper = (v2, v1) if order == "upper_lower" else (v1, v2)
                break

        if lower is None or upper is None:
            return []

        rows = table_group.get("rows", [])
        if not rows:
            return []

        q_terms = set(re.findall(r"[a-z0-9]+", question.lower()))
        best_col = None
        best_overlap = -1
        for col in rows[0].keys():
            col_terms = set(re.findall(r"[a-z0-9]+", col.lower()))
            overlap = len(col_terms & q_terms)
            num_matches = sum(
                1
                for r in rows
                if not is_summary_row(r)
                and (val := clean_number(r.get(col))) is not None
                and lower < val < upper
            )
            if num_matches > 0 and (overlap > best_overlap or best_col is None):
                best_overlap = overlap
                best_col = col

        if not best_col:
            return []

        cell_links = table_group.get("cell_links", [])
        witnesses = []
        for r_idx, r in enumerate(rows):
            if is_summary_row(r):
                continue
            val = clean_number(r.get(best_col))
            if val is not None and lower < val < upper:
                entity = row_primary_entity(r)
                row_links = tuple(
                    dict.fromkeys(
                        link["url"]
                        for link in cell_links
                        if link.get("row_index") == r_idx and link.get("url")
                    )
                )
                bridge = (entity,) if entity else ()
                witnesses.append(
                    TableWitness(
                        row_indices=(r_idx,),
                        operator="numeric_interval",
                        evidence_columns=(best_col,),
                        bridge_entities=bridge,
                        intermediate_values={
                            "column": best_col,
                            "lower": lower,
                            "upper": upper,
                            "matched_value": val,
                        },
                        hyperlinks=row_links,
                        confidence=1.0,
                    )
                )
        return witnesses

    def plan_frequency_and_latest(
        self, question: str, table_group: dict[str, Any]
    ) -> list[TableWitness]:
        """Operator 2 & 4: frequency / count + latest / earliest (e.g. runner-up most frequently -> latest)."""
        has_freq = bool(
            re.search(
                r"\b(most frequently|most often|frequently|most times|highest number of times)\b",
                question,
                re.I,
            )
        )
        if not has_freq:
            return []
        rows = table_group.get("rows", [])
        if not rows:
            return []

        target_col = None
        if re.search(r"runner-?up", question, re.I):
            for col in rows[0].keys():
                if re.search(r"runner", col, re.I):
                    target_col = col
                    break
        elif re.search(r"champion|winner|title|first place", question, re.I):
            for col in rows[0].keys():
                if re.search(r"champion|winner|title", col, re.I):
                    target_col = col
                    break
        if not target_col:
            for col in rows[0].keys():
                if any(w in col.lower() for w in ("count", "times", "frequency", "total", "appearances")):
                    target_col = col
                    break

        if not target_col:
            return []

        max_count = -1
        best_row_idx = None
        for i, row in enumerate(rows):
            if is_summary_row(row):
                continue
            val_str = str(row.get(target_col, ""))
            match = re.search(r"^\s*(\d+)", val_str)
            if match:
                cnt = int(match.group(1))
                if cnt > max_count:
                    max_count = cnt
                    best_row_idx = i

        if best_row_idx is None:
            return []

        best_row = rows[best_row_idx]
        entity = row_primary_entity(best_row)
        cell_links = table_group.get("cell_links", [])

        has_latest = bool(
            re.search(r"\b(most recent|latest|last|newest)\b", question, re.I)
        )
        has_earliest = bool(
            re.search(r"\b(earliest|first|oldest)\b", question, re.I)
        )

        target_links = [
            link
            for link in cell_links
            if link.get("row_index") == best_row_idx
            and link.get("column_name") == target_col
            and link.get("url")
        ]

        bridge_entities = [entity] if entity else []
        selected_links = []

        if (has_latest or has_earliest) and target_links:
            def extract_year(link: dict[str, Any]) -> int:
                years = re.findall(r"(?:19|20)\d{2}", link.get("url", ""))
                return max((int(y) for y in years), default=0)

            sorted_links = sorted(target_links, key=extract_year, reverse=has_latest)
            best_link = sorted_links[0]
            selected_links.append(best_link["url"])
            champ_name = re.sub(r"^/wiki/|_", " ", best_link["url"]).strip()
            bridge_entities.append(champ_name)
        else:
            selected_links.extend(link["url"] for link in target_links)

        return [
            TableWitness(
                row_indices=(best_row_idx,),
                operator="frequency_and_latest" if (has_latest or has_earliest) else "frequency",
                evidence_columns=(target_col,),
                bridge_entities=tuple(bridge_entities),
                intermediate_values={
                    "entity": entity,
                    "max_count": max_count,
                    "column": target_col,
                },
                hyperlinks=tuple(selected_links),
                confidence=1.0,
            )
        ]

    def plan_extremum(
        self, question: str, table_group: dict[str, Any]
    ) -> list[TableWitness]:
        """Operator: argmax / argmin on numeric or ordinal columns."""
        is_max = bool(
            re.search(
                r"\b(highest|largest|most|maximum|greatest|tallest|longest|heaviest|widest|fastest)\b",
                question,
                re.I,
            )
        )
        is_min = bool(
            re.search(
                r"\b(lowest|smallest|least|minimum|shortest|cheapest|slowest)\b",
                question,
                re.I,
            )
        )
        if not is_max and not is_min:
            return []

        rows = table_group.get("rows", [])
        if not rows:
            return []

        q_terms = set(re.findall(r"[a-z0-9]+", question.lower()))
        best_col = None
        best_score = -1
        for col in rows[0].keys():
            if "rank" in col.lower():
                continue
            col_terms = set(re.findall(r"[a-z0-9]+", col.lower()))
            numeric_vals = [
                clean_number(r.get(col))
                for r in rows
                if not is_summary_row(r) and clean_number(r.get(col)) is not None
            ]
            if len(numeric_vals) >= max(len(rows) // 3, 2):
                score = len(col_terms & q_terms) * 10 + len(numeric_vals)
                if score > best_score:
                    best_score = score
                    best_col = col

        if not best_col:
            return []

        valid_rows = [
            (i, r, clean_number(r.get(best_col)))
            for i, r in enumerate(rows)
            if not is_summary_row(r) and clean_number(r.get(best_col)) is not None
        ]
        if not valid_rows:
            return []

        target_row = max(valid_rows, key=lambda x: x[2]) if is_max else min(valid_rows, key=lambda x: x[2])
        best_r_idx, r_dict, extremum_val = target_row
        entity = row_primary_entity(r_dict)
        cell_links = table_group.get("cell_links", [])
        row_links = tuple(
            dict.fromkeys(
                link["url"]
                for link in cell_links
                if link.get("row_index") == best_r_idx and link.get("url")
            )
        )

        return [
            TableWitness(
                row_indices=(best_r_idx,),
                operator="argmax" if is_max else "argmin",
                evidence_columns=(best_col,),
                bridge_entities=(entity,) if entity else (),
                intermediate_values={"column": best_col, "value": extremum_val},
                hyperlinks=row_links,
                confidence=0.95,
            )
        ]

    def plan_text_condition(
        self,
        question: str,
        table_group: dict[str, Any],
        text_passages: list[dict[str, Any]] | None,
    ) -> list[TableWitness]:
        """Operator: cross-modal text condition matcher (e.g. signed by label, album by a woman)."""
        if not text_passages:
            return []
        rows = table_group.get("rows", [])
        cell_links = table_group.get("cell_links", [])
        if not rows or not cell_links:
            return []

        has_label_signed = bool(
            re.search(
                r"\b(label.*signed|signed.*label|recording contract|record label)\b",
                question,
                re.I,
            )
        )
        has_woman = bool(re.search(r"\b(woman|women|female)\b", question, re.I))
        has_chart_superlative = bool(
            re.search(r"\b(billboard|chart|most weeks|longest|record)\b", question, re.I)
        )

        if not (has_label_signed and (has_woman or has_chart_superlative)):
            return []

        passages_by_id = {p["id"]: p.get("text", "") for p in text_passages}
        scored = []
        for r_idx, row in enumerate(rows):
            if is_summary_row(row):
                continue
            r_links = [
                link for link in cell_links if link.get("row_index") == r_idx and link.get("url")
            ]
            combined_text = " ".join(passages_by_id.get(link["url"], "") for link in r_links)
            if not combined_text:
                continue

            score = 0.0
            if re.search(
                r"\b(signed.*contract|recording contract|record label|signed.*with)\b",
                combined_text,
                re.I,
            ):
                score += 3.0
            if has_woman and re.search(
                r"\b(female|woman|singer-songwriter|she|her)\b", combined_text, re.I
            ):
                score += 2.0
            if has_chart_superlative and re.search(
                r"\b(billboard|longer than any|longest|record|top position)\b",
                combined_text,
                re.I,
            ):
                score += 2.0

            if score >= 4.0:
                entity = row_primary_entity(row)
                bridge = [entity] if entity else []
                for link in r_links:
                    val = link.get("cell_value")
                    if val and val not in bridge:
                        bridge.append(val)
                urls = tuple(dict.fromkeys(link["url"] for link in r_links))
                scored.append((score, r_idx, tuple(bridge), urls))

        if not scored:
            return []
        scored.sort(reverse=True, key=lambda x: x[0])
        best_score, best_r_idx, best_bridge, best_urls = scored[0]
        return [
            TableWitness(
                row_indices=(best_r_idx,),
                operator="text_condition",
                evidence_columns=tuple(rows[best_r_idx].keys()),
                bridge_entities=best_bridge,
                intermediate_values={"score": best_score},
                hyperlinks=best_urls,
                confidence=0.9,
            )
        ]

    def plan(
        self,
        question: str,
        table_groups: list[dict[str, Any]],
        text_passages: list[dict[str, Any]] | None = None,
    ) -> list[TableWitness]:
        """Run all operators in priority order and return identified table witnesses."""
        witnesses: list[TableWitness] = []
        for group in table_groups:
            # 1. Numeric interval
            int_w = self.plan_numeric_interval(question, group)
            if int_w:
                witnesses.extend(int_w)
                continue

            # 2. Frequency + latest / earliest
            freq_w = self.plan_frequency_and_latest(question, group)
            if freq_w:
                witnesses.extend(freq_w)
                continue

            # 3. Text condition
            text_w = self.plan_text_condition(question, group, text_passages)
            if text_w:
                witnesses.extend(text_w)
                continue

            # 4. Extremum (argmax / argmin)
            ext_w = self.plan_extremum(question, group)
            if ext_w:
                witnesses.extend(ext_w)

        return witnesses
