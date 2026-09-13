"""Shared, provider-neutral HTTP reliability settings."""

from __future__ import annotations

import os


def request_timeout_seconds() -> float:
    return float(os.environ.get("LLM_REQUEST_TIMEOUT_SECONDS", "120"))


def sdk_max_retries() -> int:
    return int(os.environ.get("LLM_SDK_MAX_RETRIES", "2"))
