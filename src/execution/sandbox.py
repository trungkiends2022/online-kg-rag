"""Chạy thử code do LLM sinh, trong môi trường giới hạn (không import, không I/O, có timeout)."""

from __future__ import annotations

import signal
import contextlib
from dataclasses import dataclass
from typing import Any

from src.kg.online_kg import OnlineKG


class TimeoutException(Exception):
    pass


@contextlib.contextmanager
def _time_limit(seconds: int):
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


SAFE_BUILTINS = {
    "len": len, "sum": sum, "sorted": sorted, "min": min, "max": max,
    "list": list, "set": set, "dict": dict, "str": str, "int": int,
    "float": float, "bool": bool, "range": range, "enumerate": enumerate,
    "filter": filter, "map": map, "any": any, "all": all,
}


class SandboxExecutor:
    def run(self, code: str, kg: OnlineKG, timeout_sec: int = 5) -> ExecResult:
        local_env: dict = {"kg": kg}
        global_env = {"__builtins__": SAFE_BUILTINS}
        try:
            with _time_limit(timeout_sec):
                exec(code, global_env, local_env)  # noqa: S102 -- sandboxed builtins only
        except TimeoutException as e:
            return ExecResult(success=False, error=str(e))
        except Exception as e:  # noqa: BLE001 -- bắt mọi lỗi runtime của code sinh ra
            return ExecResult(success=False, error=f"{type(e).__name__}: {e}")

        result = local_env.get("result")
        is_empty = result is None or (hasattr(result, "__len__") and len(result) == 0)
        return ExecResult(success=True, value=result, is_empty=is_empty)
