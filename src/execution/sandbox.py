"""Chạy thử code do LLM sinh, trong môi trường giới hạn (không import, không I/O, có timeout)."""

from __future__ import annotations

import signal
import contextlib
import platform
from dataclasses import dataclass
from typing import Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from src.kg.online_kg import OnlineKG
from src.kg.schema import EvidenceRef


class TimeoutException(Exception):
    pass


@contextlib.contextmanager
def _time_limit(seconds: int):
    """Timeout context manager - use signal on Unix/Linux, threading on Windows."""
    if platform.system() == "Windows":
        # Windows doesn't support signal.SIGALRM, use threading instead
        yield
    else:
        # Unix/Linux: use signal.SIGALRM
        def handler(signum, frame):
            raise TimeoutException("Code execution timed out")

        old = signal.signal(signal.SIGALRM, handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)


@dataclass
class ExecResult:
    success: bool
    value: Any = None
    error: str = ""
    is_empty: bool = False
    evidence: tuple[EvidenceRef, ...] = ()
    accessed_edges: int = 0
    step_values: dict[str, Any] | None = None
    operator_trace: tuple[str, ...] = ()


class TracingKG:
    """Expose the safe KG API while recording provenance of returned edges."""

    def __init__(self, kg: OnlineKG):
        self._kg = kg
        self._evidence: set[EvidenceRef] = set()

    @property
    def evidence(self) -> tuple[EvidenceRef, ...]:
        return tuple(sorted(
            self._evidence,
            key=lambda item: (item.source_type, item.source_id, item.head, item.relation, item.tail),
        ))

    def get_neighbors(self, entity: str, relation: str | None = None) -> list[str]:
        resolved = self._kg._resolve_entity(entity)
        values = self._kg.get_neighbors(entity, relation)
        for tail in values:
            self._evidence.update(self._kg.get_evidence(resolved, tail, relation))
        return values

    def get_sources(self, entity: str, relation: str | None = None) -> list[str]:
        resolved = self._kg._resolve_entity(entity)
        values = self._kg.get_sources(entity, relation)
        for head in values:
            self._evidence.update(self._kg.get_evidence(head, resolved, relation))
        return values

    def get_relations(self, entity: str) -> list[str]:
        return self._kg.get_relations(entity)

    @staticmethod
    def filter(entities: list[str], predicate) -> list[str]:
        return [entity for entity in entities if predicate(entity)]

    def get_provenance(self, head: str, tail: str):
        self._evidence.update(self._kg.get_evidence(head, tail))
        return self._kg.get_provenance(head, tail)


SAFE_BUILTINS = {
    "len": len, "sum": sum, "sorted": sorted, "min": min, "max": max,
    "list": list, "set": set, "dict": dict, "str": str, "int": int,
    "float": float, "bool": bool, "range": range, "enumerate": enumerate,
    "filter": filter, "map": map, "zip": zip, "any": any, "all": all,
}


class SandboxExecutor:
    def run(self, code: str, kg: OnlineKG, timeout_sec: int = 5) -> ExecResult:
        # Use one namespace so functions/lambdas defined by generated code can
        # resolve ``kg``. With separate globals/locals, top-level expressions
        # worked but function bodies raised ``NameError: kg is not defined``.
        tracing_kg = TracingKG(kg)
        exec_env: dict = {"__builtins__": SAFE_BUILTINS, "kg": tracing_kg}

        def failed(error: str) -> ExecResult:
            evidence = tracing_kg.evidence
            return ExecResult(False, error=error, evidence=evidence, accessed_edges=len(evidence))
        
        if platform.system() == "Windows":
            # Windows: use ThreadPoolExecutor for timeout
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(exec, code, exec_env, exec_env)  # noqa: S102
                    future.result(timeout=timeout_sec)
            except TimeoutError:
                return failed("Code execution timed out")
            except Exception as e:  # noqa: BLE001 -- bắt mọi lỗi runtime của code sinh ra
                return failed(f"{type(e).__name__}: {e}")
        else:
            # Unix/Linux: use signal.SIGALRM
            try:
                with _time_limit(timeout_sec):
                    exec(code, exec_env, exec_env)  # noqa: S102 -- sandboxed builtins only
            except TimeoutException as e:
                return failed(str(e))
            except Exception as e:  # noqa: BLE001 -- bắt mọi lỗi runtime của code sinh ra
                return failed(f"{type(e).__name__}: {e}")

        result = exec_env.get("result")
        is_empty = result is None or (hasattr(result, "__len__") and len(result) == 0)
        evidence = tracing_kg.evidence
        return ExecResult(
            success=True,
            value=result,
            is_empty=is_empty,
            evidence=evidence,
            accessed_edges=len(evidence),
        )
