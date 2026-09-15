"""Typed, provenance-preserving numerical IR for the Online-KG ablation."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from src.execution.sandbox import ExecResult, TracingKG
from src.llm.client import llm_call
from src.planning.planner import ReasoningPath
from src.planning.operation_intent import format_operation_intent, infer_operation_intent

if TYPE_CHECKING:
    from src.kg.online_kg import OnlineKG


SUPPORTED_OPERATORS = frozenset({
    "lookup", "const", "add", "subtract", "multiply", "divide", "exp",
    "greater", "compare", "table_sum", "table_average", "table_max", "table_min",
    "less", "negate", "count", "range", "argmax", "argmin",
    "topk_argmax", "topk_argmin", "kth_argmax", "kth_argmin",
    "filter_greater", "filter_less",
})
NUMERICAL_IR_MAX_TOKENS = 2048
_REF_RE = re.compile(r"^v\d+$")
_NUMBER_RE = re.compile(r"[-+]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?")


class NumericalIRSynthesisError(ValueError):
    def __init__(self, message: str, *, parse_valid: bool, schema_valid: bool):
        super().__init__(message)
        self.parse_valid = parse_valid
        self.schema_valid = schema_valid


@dataclass(frozen=True)
class IRStep:
    id: str
    op: str
    arguments: Any
    unit: str | None = None


@dataclass(frozen=True)
class NumericalProgram:
    steps: tuple[IRStep, ...]
    result: str
    repair_count: int = 0

    @classmethod
    def from_dict(cls, raw: dict[str, Any], *, repair_count: int = 0) -> "NumericalProgram":
        if not isinstance(raw, dict) or not isinstance(raw.get("steps"), list):
            raise ValueError("IR must be an object containing a steps list")
        steps = tuple(
            IRStep(
                id=str(item.get("id", "")),
                op=str(item.get("op", "")),
                arguments=item.get("arguments"),
                unit=item.get("unit"),
            )
            for item in raw["steps"]
            if isinstance(item, dict)
        )
        program = cls(
            steps=steps, result=str(raw.get("result", "")), repair_count=repair_count
        )
        program.validate()
        return program

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [
                {"id": step.id, "op": step.op, "arguments": step.arguments, "unit": step.unit}
                for step in self.steps
            ],
            "result": self.result,
            "repair_count": self.repair_count,
        }

    def validate(self) -> None:
        seen: set[str] = set()
        binary = {"subtract", "divide", "exp", "greater", "less", "compare"}
        variadic = {"add", "multiply", "table_sum", "table_average", "table_max", "table_min"}
        for step in self.steps:
            if not _REF_RE.fullmatch(step.id) or step.id in seen:
                raise ValueError(f"invalid or duplicate step id: {step.id!r}")
            if step.op not in SUPPORTED_OPERATORS:
                raise ValueError(f"unsupported IR operator: {step.op!r}")
            for ref in _references(step.arguments):
                if ref not in seen:
                    raise ValueError(f"forward or unknown reference {ref!r} in {step.id}")
            if step.op == "lookup":
                args = step.arguments
                if not isinstance(args, dict) or not isinstance(args.get("entity"), str):
                    raise ValueError("lookup requires string entity and relation")
                if not isinstance(args.get("relation"), str):
                    raise ValueError("lookup requires string entity and relation")
                if args.get("direction", "neighbors") not in {"neighbors", "sources"}:
                    raise ValueError("lookup direction must be neighbors or sources")
            elif step.op in binary:
                if not isinstance(step.arguments, (list, tuple)) or len(step.arguments) != 2:
                    raise ValueError(f"{step.op} requires exactly two operands")
            elif step.op in variadic:
                if not isinstance(step.arguments, (list, tuple)) or not step.arguments:
                    raise ValueError(f"{step.op} requires one or more operands")
            elif step.op in {"negate", "range", "argmax", "argmin"}:
                if not isinstance(step.arguments, (list, tuple)) or not step.arguments:
                    raise ValueError(f"{step.op} requires a non-empty list")
            elif step.op == "count" and step.arguments in (None, [], {}):
                raise ValueError("count requires a collection")
            elif step.op in {"topk_argmax", "topk_argmin", "kth_argmax", "kth_argmin"}:
                if not isinstance(step.arguments, dict) or not {"items", "k"} <= set(step.arguments):
                    raise ValueError(f"{step.op} requires items and k")
            elif step.op in {"filter_greater", "filter_less"}:
                if not isinstance(step.arguments, dict) or not {"items", "threshold"} <= set(step.arguments):
                    raise ValueError(f"{step.op} requires items and threshold")
            seen.add(step.id)
        if not self.steps or self.result not in seen:
            raise ValueError("result must reference an existing IR step")


def _references(value: Any):
    if isinstance(value, str) and _REF_RE.fullmatch(value):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _references(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _references(item)


def canonicalize_model_ir(raw: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Repair only unambiguous wrappers; never choose an operator or operand."""
    if not isinstance(raw, dict) or not isinstance(raw.get("steps"), list):
        return raw, 0
    repaired = {
        **raw,
        "steps": [dict(step) if isinstance(step, dict) else step for step in raw["steps"]],
    }
    count = 0
    binary_keys = (
        ("left", "right"), ("a", "b"), ("x", "y"),
        ("minuend", "subtrahend"), ("numerator", "denominator"),
        ("base", "exponent"),
    )
    binary_ops = {"subtract", "divide", "exp", "greater", "less", "compare"}
    variadic_ops = {"add", "multiply", "table_sum", "table_average", "table_max", "table_min"}
    for step in repaired["steps"]:
        if not isinstance(step, dict):
            continue
        args = step.get("arguments")
        if step.get("op") in binary_ops and isinstance(args, dict):
            replacement = args.get("operands") if set(args) == {"operands"} else None
            if replacement is None:
                for left, right in binary_keys:
                    if set(args) == {left, right}:
                        replacement = [args[left], args[right]]
                        break
            if isinstance(replacement, list):
                step["arguments"] = replacement
                count += 1
        elif step.get("op") in variadic_ops and isinstance(args, dict):
            for key in ("operands", "values", "items"):
                if set(args) == {key} and isinstance(args[key], list):
                    step["arguments"] = args[key]
                    count += 1
                    break
    return repaired, count


def _number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("boolean is not a numeric operand")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, (list, tuple)) and len(value) == 1:
        return _number(value[0])
    text = str(value).strip().replace("$", "")
    match = _NUMBER_RE.search(text)
    if not match:
        raise ValueError(f"cannot parse numeric operand: {value!r}")
    number = float(match.group(0).replace(",", ""))
    if "(" in text and ")" in text and number > 0:
        number = -number
    return number


class NumericalIRExecutor:
    """Execute a validated closed-operator program and retain lookup evidence."""

    def run(self, program: NumericalProgram | dict[str, Any] | str, kg: "OnlineKG") -> ExecResult:
        tracing_kg = TracingKG(kg)
        try:
            if isinstance(program, str):
                program = NumericalProgram.from_dict(json.loads(program))
            elif isinstance(program, dict):
                program = NumericalProgram.from_dict(program)
            else:
                program.validate()
            values: dict[str, Any] = {}
            for step in program.steps:
                values[step.id] = self._execute(step, values, tracing_kg)
            value = values[program.result]
            evidence = tracing_kg.evidence
            empty = value is None or (hasattr(value, "__len__") and len(value) == 0)
            return ExecResult(
                True, value=value, is_empty=empty, evidence=evidence,
                accessed_edges=len(evidence), step_values=values,
                operator_trace=tuple(step.op for step in program.steps),
            )
        except Exception as exc:  # malformed model programs are candidate failures
            evidence = tracing_kg.evidence
            return ExecResult(
                False, error=f"{type(exc).__name__}: {exc}", is_empty=True,
                evidence=evidence, accessed_edges=len(evidence),
            )

    @staticmethod
    def _resolve(value: Any, values: dict[str, Any]) -> Any:
        if isinstance(value, str) and _REF_RE.fullmatch(value):
            return values[value]
        if isinstance(value, list):
            return [NumericalIRExecutor._resolve(item, values) for item in value]
        if isinstance(value, dict):
            return {
                key: NumericalIRExecutor._resolve(item, values)
                for key, item in value.items()
            }
        return value

    def _execute(self, step: IRStep, values: dict[str, Any], kg: TracingKG) -> Any:
        args = step.arguments
        if step.op == "lookup":
            method = kg.get_sources if args.get("direction", "neighbors") == "sources" else kg.get_neighbors
            found = method(args["entity"], args["relation"])
            index = args.get("index")
            return found[int(index)] if index is not None else found
        if step.op == "const":
            return args.get("value") if isinstance(args, dict) else args

        resolved = self._resolve(args, values)
        if step.op in {"argmax", "argmin", "topk_argmax", "topk_argmin", "kth_argmax", "kth_argmin", "filter_greater", "filter_less"}:
            config = resolved if isinstance(resolved, dict) else {"items": resolved}
            items = config.get("items", resolved)
            pairs = []
            for item in items:
                if isinstance(item, dict) and "label" in item and "value" in item:
                    pairs.append((str(item["label"]), _number(item["value"])))
                elif isinstance(item, (list, tuple)) and len(item) == 2:
                    pairs.append((str(item[0]), _number(item[1])))
                else:
                    raise ValueError(f"{step.op} items require label/value pairs")
            reverse = step.op in {"argmax", "topk_argmax", "kth_argmax"}
            ranked = sorted(pairs, key=lambda pair: (pair[1], pair[0]), reverse=reverse)
            if step.op in {"argmax", "argmin"}:
                return ranked[0][0]
            if step.op in {"topk_argmax", "topk_argmin"}:
                return [label for label, _ in ranked[:int(_number(config["k"]))]]
            if step.op in {"kth_argmax", "kth_argmin"}:
                return ranked[int(_number(config["k"])) - 1][0]
            threshold = _number(config["threshold"])
            predicate = (lambda value: value > threshold) if step.op == "filter_greater" else (lambda value: value < threshold)
            return [label for label, value in pairs if predicate(value)]
        operands = list(resolved.values()) if isinstance(resolved, dict) else resolved
        if not isinstance(operands, list):
            operands = [operands]
        if step.op.startswith("table_") and len(operands) == 1 and isinstance(operands[0], list):
            operands = operands[0]
        if step.op == "count":
            collection = operands[0] if len(operands) == 1 and isinstance(operands[0], list) else operands
            return len(collection)
        nums = [_number(item) for item in operands]
        if step.op in {"add", "table_sum"}:
            return sum(nums)
        if step.op == "subtract":
            return nums[0] - nums[1]
        if step.op == "multiply":
            return math.prod(nums)
        if step.op == "divide":
            return nums[0] / nums[1]
        if step.op == "exp":
            return nums[0] ** nums[1]
        if step.op in {"greater", "compare"}:
            return nums[0] > nums[1]
        if step.op == "less":
            return nums[0] < nums[1]
        if step.op == "negate":
            return -nums[0]
        if step.op == "range":
            return [max(nums), min(nums)]
        if step.op == "table_average":
            return sum(nums) / len(nums)
        if step.op == "table_max":
            return max(nums)
        if step.op == "table_min":
            return min(nums)
        raise ValueError(f"unsupported operator: {step.op}")


class NumericalIRSynthesizer:
    """Generate a JSON numerical program instead of unrestricted Python."""

    def __init__(self, temperature: float | None = None):
        self.temperature = temperature

    def synthesize(
        self, path: ReasoningPath, question: str, kg: "OnlineKG", retries: int = 1,
    ) -> NumericalProgram:
        question_terms = set(re.findall(r"[a-z0-9]+", question.lower()))
        ranked_edges = []
        seen_edges = set()
        for position, (head, tail, data) in enumerate(kg.graph.edges(data=True)):
            provenance = data.get("provenance")
            source_type = getattr(provenance, "source_type", "unknown")
            identity = (str(head), str(data["relation"]), str(tail), source_type)
            if identity in seen_edges:
                continue
            seen_edges.add(identity)
            rendered = " ".join(map(str, identity[:3])).lower()
            edge_terms = set(re.findall(r"[a-z0-9]+", rendered))
            overlap = len(question_terms & edge_terms)
            phrase_bonus = sum(
                len(term) for term in question_terms
                if len(term) >= 4 and term in rendered
            )
            ranked_edges.append((overlap, phrase_bonus, -position, {
                "head": head,
                "relation": data["relation"],
                "tail": tail,
                "source_type": source_type,
            }))
        ranked_edges.sort(key=lambda item: item[:3], reverse=True)
        edges = [item[3] for item in ranked_edges[:200]]
        operation_intent = infer_operation_intent(question, kg)
        base_prompt = f"""
Question: {question}
Reasoning path: {json.dumps([s.__dict__ for s in path.steps], ensure_ascii=False)}
KG edges: {json.dumps(edges, ensure_ascii=False)}
Numerical operation intent inferred from question and KG schema only:
{format_operation_intent(operation_intent)}

Create an executable numerical IR as one JSON object. Allowed operators:
lookup, const, add, subtract, multiply, divide, exp, greater, compare,
less, negate, count, range, table_sum, table_average, table_max, table_min,
argmax, argmin, topk_argmax, topk_argmin, kth_argmax, kth_argmin,
filter_greater, filter_less.
For temporal change "from A to B", preserve the signed result and compute B - A.
Do not convert a decline to an absolute positive magnitude unless explicitly asked.
Each step has id v0, v1, ...; op; arguments; and optional unit.
lookup arguments are {{"entity": string, "relation": string,
"direction": "neighbors"|"sources", optional "index": integer}}.
Other arguments contain constants or references to earlier step IDs. Use const for
explicit question constants such as 100. Ratio is divide(a,b); percentage is
multiply(divide(a,b),100) with unit "percent". Do not put evidence in the JSON:
lookup provenance is captured automatically during execution.
Follow the inferred operation intent. In particular, when it says to add displayed
percentage cells, lookup those percentage values and add them directly; do not
introduce count lookups, weighting, or a denominator absent from the question.
Ground every operand that is available in the KG. Before emitting an aggregation,
enumerate the complete requested scope: every named entity, applicable table row,
time period, or category. Do not silently omit intermediate rows. For periods such
as "three months ended March", include all applicable dated rows through March,
not only the row whose date label is March.
Match row/entity wording exactly. Do not substitute a related accounting row
(for example, "additions to plant and equipment") for the row named by the
question (for example, "capital expenditures on a GAAP basis").
Preserve displayed table magnitudes for the final answer; do not rescale a table
value solely because a header says thousands or millions. When combining text and
table operands that explicitly use different units, normalize them to the same
unit before arithmetic.
If the question is boolean/comparative (e.g. outperform), retrieve both compared
values and use greater/compare. If the question asks a total but an exact total
cell exists, prefer that cell unless the reasoning path explicitly requires
table_sum over a complete displayed row or set.
Selection operators consume label/value pairs such as
[{{"label":"Ontario","value":"v0"}},{{"label":"Quebec","value":"v1"}}].
Use argmax/argmin for one label; topk_argmax/topk_argmin with
{{"items":[...],"k":3}} for a list; kth_argmax/kth_argmin for the kth label.
Use filter_greater/filter_less with {{"items":[...],"threshold":0}} and then
count when the question asks how many satisfy a condition. HiTab range returns
[maximum, minimum]. Use negate for an explicitly requested opposite sign.
For EVERY arithmetic operator, arguments MUST be a JSON array. Binary operators
subtract/divide/exp/greater/compare MUST have exactly two elements. Never use an
object such as {{"left": ..., "right": ...}} for arithmetic arguments.
Valid percentage example:
{{"steps":[
  {{"id":"v0","op":"lookup","arguments":{{"entity":"row entity","relation":"year_value","direction":"neighbors","index":0}}}},
  {{"id":"v1","op":"lookup","arguments":{{"entity":"other entity","relation":"value","direction":"neighbors","index":0}}}},
  {{"id":"v2","op":"subtract","arguments":["v1","v0"]}},
  {{"id":"v3","op":"divide","arguments":["v2","v0"]}},
  {{"id":"v4","op":"const","arguments":100}},
  {{"id":"v5","op":"multiply","arguments":["v3","v4"],"unit":"percent"}}
],"result":"v5"}}
Return only JSON: {{"steps": [...], "result": "vN"}}.
"""
        last_error = "empty response"
        parse_valid = False
        schema_valid = False
        for attempt in range(retries + 1):
            prompt = base_prompt if not attempt else base_prompt + f"\nPrevious IR invalid: {last_error}. Return corrected JSON only."
            kwargs = {"max_tokens": NUMERICAL_IR_MAX_TOKENS}
            if self.temperature is not None:
                kwargs["temperature"] = self.temperature
            raw = llm_call(prompt, **kwargs).strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parse_valid = False
            schema_valid = False
            try:
                decoded = json.loads(raw)
                parse_valid = True
                decoded, repair_count = canonicalize_model_ir(decoded)
                program = NumericalProgram.from_dict(decoded, repair_count=repair_count)
                schema_valid = True
                relations = set(kg.summary()["relations"])
                for step in program.steps:
                    if step.op == "lookup" and kg.normalize_relation(step.arguments["relation"]) not in relations:
                        raise ValueError(f"relation not present in KG: {step.arguments['relation']}")
                return program
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                last_error = str(exc)
        raise NumericalIRSynthesisError(
            f"LLM could not generate valid numerical IR: {last_error}",
            parse_valid=parse_valid, schema_valid=schema_valid,
        )
