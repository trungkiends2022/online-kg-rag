"""Sinh code Python thực thi 1 reasoning path, chỉ được gọi qua API giới hạn của kg."""

from __future__ import annotations

import ast
import json
from typing import TYPE_CHECKING

from src.planning.planner import ReasoningPath
from src.llm.client import llm_call

if TYPE_CHECKING:
    from src.kg.online_kg import OnlineKG

KG_API_DOC = """
API khả dụng trên biến `kg` (đối tượng OnlineKG):
    kg.get_neighbors(entity: str, relation: str = None) -> list[str]
    kg.get_sources(entity: str, relation: str = None) -> list[str]
    kg.get_relations(entity: str) -> list[str]
    kg.filter(entities: list[str], predicate: Callable[[str], bool]) -> list[str]
Code PHẢI gán kết quả cuối cùng vào biến `result`.
Không được import, không được mở file, không được gọi network.
`get_neighbors` đi từ head tới tail; `get_sources` đi ngược từ tail về head.
Tên relation được chuẩn hóa tự động (camelCase/space/snake_case).
Chỉ dùng entity và relation có trong KG được cung cấp. Không tự đoán relation.
Để tìm head từ một tail đã biết, PHẢI dùng `get_sources`, không dùng keyword
`obj`/`subject` vì các keyword này không tồn tại.
Không được gán cứng câu trả lời vào `result`; `result` phải được suy ra từ lời gọi KG.
"""


_API_SIGNATURES = {
    "get_neighbors": (2, {"entity", "relation"}),
    "get_sources": (2, {"entity", "relation"}),
    "get_relations": (1, {"entity"}),
    "filter": (2, {"entities", "predicate"}),
}


class CodeSynthesizer:
    @staticmethod
    def _validate_code(code: str, kg: "OnlineKG | None" = None) -> None:
        """Reject compilable code that cannot use the public KG API correctly."""
        tree = ast.parse(code)
        allowed_relations = set(kg.summary()["relations"]) if kg is not None else None
        assignments: dict[str, ast.expr] = {}
        for candidate in ast.walk(tree):
            if isinstance(candidate, ast.Assign):
                for target in candidate.targets:
                    if isinstance(target, ast.Name):
                        assignments[target.id] = candidate.value
            elif isinstance(candidate, ast.AnnAssign) and isinstance(candidate.target, ast.Name):
                assignments[candidate.target.id] = candidate.value

        def static_string(expr: ast.expr | None, seen: set[str] | None = None) -> bool:
            if isinstance(expr, ast.Constant):
                return isinstance(expr.value, str)
            if isinstance(expr, ast.Name):
                visited = seen or set()
                if expr.id in visited:
                    return False
                return static_string(assignments.get(expr.id), visited | {expr.id})
            return False

        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                value = node.value
                if any(isinstance(target, ast.Name) and target.id == "result" for target in targets):
                    if static_string(value):
                        raise ValueError("hard-coded string result, directly or through a variable")

            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "kg"
            ):
                continue
            method = func.attr
            if method not in _API_SIGNATURES:
                raise ValueError(f"unsupported kg method: {method}")
            max_args, allowed_keywords = _API_SIGNATURES[method]
            if len(node.args) > max_args:
                raise ValueError(f"kg.{method} accepts at most {max_args} positional arguments")
            bad_keywords = {
                keyword.arg for keyword in node.keywords
                if keyword.arg is None or keyword.arg not in allowed_keywords
            }
            if bad_keywords:
                names = ", ".join(sorted(str(name) for name in bad_keywords))
                raise ValueError(f"invalid keyword(s) for kg.{method}: {names}")

            relation_node = None
            if method in {"get_neighbors", "get_sources"}:
                if len(node.args) >= 2:
                    relation_node = node.args[1]
                else:
                    relation_node = next(
                        (keyword.value for keyword in node.keywords if keyword.arg == "relation"),
                        None,
                    )
            if (
                allowed_relations is not None
                and isinstance(relation_node, ast.Constant)
                and isinstance(relation_node.value, str)
            ):
                normalized = kg.normalize_relation(relation_node.value)
                if normalized not in allowed_relations:
                    raise ValueError(f"relation not present in KG: {relation_node.value}")
                entity_node = node.args[0] if node.args else next(
                    (keyword.value for keyword in node.keywords if keyword.arg == "entity"),
                    None,
                )
                if isinstance(entity_node, ast.Constant) and isinstance(entity_node.value, str):
                    entity = kg._resolve_entity(entity_node.value)
                    if entity in kg.graph:
                        has_outgoing = any(
                            data.get("relation") == normalized
                            for _, _, data in kg.graph.out_edges(entity, data=True)
                        )
                        has_incoming = any(
                            data.get("relation") == normalized
                            for _, _, data in kg.graph.in_edges(entity, data=True)
                        )
                        if method == "get_neighbors" and not has_outgoing and has_incoming:
                            raise ValueError(
                                f"wrong edge direction for {entity_node.value!r}/{normalized}: "
                                "use get_sources"
                            )
                        if method == "get_sources" and not has_incoming and has_outgoing:
                            raise ValueError(
                                f"wrong edge direction for {entity_node.value!r}/{normalized}: "
                                "use get_neighbors"
                            )

    def synthesize(
        self,
        path: ReasoningPath,
        question: str,
        kg: "OnlineKG | None" = None,
        retries: int = 1,
    ) -> str:
        kg_context = ""
        if kg is not None:
            edges = [
                {"head": head, "relation": data["relation"], "tail": tail}
                for head, tail, data in list(kg.graph.edges(data=True))[:100]
            ]
            kg_context = (
                f"\nEntities hợp lệ: {list(kg.graph.nodes())[:100]}"
                f"\nRelations hợp lệ: {kg.summary()['relations']}"
                f"\nCác edge mẫu: {json.dumps(edges, ensure_ascii=False)}\n"
            )
        base_prompt = f"""
        Question: {question}
        Reasoning path: {json.dumps([s.__dict__ for s in path.steps], ensure_ascii=False)}
        {KG_API_DOC}
        {kg_context}

        Viết code Python thực hiện đúng reasoning path trên bằng cách gọi các hàm của `kg`.
        Chỉ trả về code, không giải thích, không markdown fence.
        """
        last_code = ""
        last_error = "empty code"
        for attempt in range(retries + 1):
            prompt = base_prompt
            if attempt:
                prompt += (
                    f"\nCode trước không hợp lệ ({last_error}):\n{last_code}\n"
                    "Viết lại code hoàn chỉnh, hợp lệ và phải gán biến result."
                )
            raw = llm_call(prompt)
            last_code = raw.strip().removeprefix("```python").removeprefix("```").removesuffix("```").strip()
            if not last_code:
                last_error = "empty code"
                continue
            try:
                compile(last_code, "<llm-generated>", "exec")
                self._validate_code(last_code, kg)
            except SyntaxError as exc:
                last_error = f"SyntaxError: {exc.msg} at line {exc.lineno}"
                continue
            except ValueError as exc:
                last_error = str(exc)
                continue
            if "result" not in last_code:
                last_error = "missing result assignment"
                continue
            return last_code
        raise ValueError(f"LLM không sinh được code hợp lệ sau {retries + 1} lần: {last_error}")
