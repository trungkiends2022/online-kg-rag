"""Shared response contract for context-grounded baseline readers.

The contract deliberately makes an unsupported answer an abstention rather
than a guess.  It mirrors OUEG's L1 answer/diagnostic split while remaining
agnostic to a baseline's internal representation.
"""

from __future__ import annotations

import json
import re


def response_contract(*, source_label: str = "context IDs") -> str:
    """Return the answer-time contract used by non-OUEG baselines."""
    return f"""Use only facts in the supplied context. Do not use pre-training, world
knowledge, or facts not present in that context. Return exactly one of:
1. `FINAL_ANSWER: <shortest answer span>` followed by
   `EVIDENCE_PATH: {{\"context_ids\":[\"{source_label} from the supplied context\"]}}`.
   Use this only when the cited context proves one answer.
2. `NEED_FOCUS: {{\"candidates\":[\"names already present in context\"],\"blocker_type\":\"candidate_collision|missing_link|conflicting_evidence|answer_type_uncertain\",\"bottleneck\":\"...\",\"needed_check\":\"...\"}}`
   when a focused context re-read would be needed to resolve a collision.
3. `UNRESOLVED: {{\"blocker_type\":\"missing_link|insufficient_evidence|conflicting_evidence|answer_type_uncertain\",\"bottleneck\":\"...\",\"needed_check\":\"...\"}}`
   when the supplied context cannot prove one answer.
Never guess, invent an answer, invent a context ID, or return a blank response."""


def parse_response(raw: str, allowed_context_ids: list[str] | set[str]) -> dict:
    """Parse and validate the shared L1-style contract.

    Bare answers and citations outside the answer-time payload are deliberately
    rejected: they cannot establish that the prediction was context-grounded.
    """
    raw = str(raw or "").strip()
    allowed = {str(value) for value in allowed_context_ids}
    unresolved = {
        "answer": "",
        "abstained": True,
        "response_valid": False,
        "evidence_context_ids": [],
        "diagnostic": None,
        "raw_response": raw,
    }
    if not raw:
        unresolved["diagnostic"] = {
            "blocker_type": "invalid_response",
            "bottleneck": "The model returned no grounded response.",
            "needed_check": "Re-read the supplied context and cite supporting IDs.",
        }
        return unresolved

    unresolved_match = re.search(r"^\s*(NEED_FOCUS|UNRESOLVED)\s*:\s*(\{.*\})\s*$", raw, re.I | re.S)
    if unresolved_match:
        try:
            diagnostic = json.loads(unresolved_match.group(2))
        except json.JSONDecodeError:
            diagnostic = None
        unresolved["response_valid"] = isinstance(diagnostic, dict)
        unresolved["diagnostic"] = diagnostic or {
            "blocker_type": "invalid_response",
            "bottleneck": "Malformed UNRESOLVED diagnostic.",
            "needed_check": "Return valid diagnostic JSON.",
        }
        return unresolved

    answer_match = re.search(
        r"^\s*FINAL_ANSWER\s*:\s*(.+?)\s*\n\s*EVIDENCE_PATH\s*:\s*(\{.*\})\s*$",
        raw,
        re.I | re.S,
    )
    if not answer_match:
        unresolved["diagnostic"] = {
            "blocker_type": "invalid_response",
            "bottleneck": "Response did not follow the grounded L1 contract.",
            "needed_check": "Return FINAL_ANSWER with cited context IDs, or UNRESOLVED.",
        }
        return unresolved
    answer = answer_match.group(1).strip()
    try:
        evidence = json.loads(answer_match.group(2))
    except json.JSONDecodeError:
        evidence = {}
    cited = evidence.get("context_ids", []) if isinstance(evidence, dict) else []
    cited = [str(value) for value in cited] if isinstance(cited, list) else []
    valid_citations = bool(cited) and set(cited).issubset(allowed)
    if not answer or not valid_citations:
        unresolved["diagnostic"] = {
            "blocker_type": "invalid_evidence_path",
            "bottleneck": "The answer has no valid citation to the supplied context.",
            "needed_check": "Cite one or more supplied context IDs, or return UNRESOLVED.",
        }
        return unresolved
    return {
        "answer": answer,
        "abstained": False,
        "response_valid": True,
        "evidence_context_ids": cited,
        "diagnostic": None,
        "raw_response": raw,
    }
