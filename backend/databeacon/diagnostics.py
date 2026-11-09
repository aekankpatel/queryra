"""Safe, public descriptions of startup failures (no secrets, ids or local paths)."""

from __future__ import annotations

import os
import re
from typing import Any

_SECRET_NAMES = re.compile(r"TOKEN|KEY|SECRET|PASSWORD|ACCOUNT_ID|DATABASE_ID|ACCESS_CODE", re.I)
_PATTERNS = [
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I),  # UUIDs (database ids)
    re.compile(r"\b[0-9a-f]{32}\b", re.I),  # account ids
    re.compile(r"\b[A-Za-z0-9_\-]{30,}\b"),  # token-like strings
    re.compile(r"(?:/[\w.\-]+){2,}"),  # file system paths
]


def redact(text: Any, limit: int = 300) -> str:
    s = str(text)
    for name, value in os.environ.items():
        if value and len(value) >= 6 and _SECRET_NAMES.search(name):
            s = s.replace(value, "[redacted]")
    for p in _PATTERNS:
        s = p.sub("[redacted]", s)
    return s[:limit]


def describe(exc: BaseException) -> str:
    """'StorageError: D1 error (HTTP 403): Authentication error' with anything sensitive removed."""
    return f"{type(exc).__name__}: {redact(exc)}"


class Unavailable:
    """Stands in for a component that could not start: every use answers 503 with the reason."""

    def __init__(self, what: str, reason: str):
        self._what, self._reason = what, reason

    def __getattr__(self, name: str):
        from fastapi import HTTPException

        raise HTTPException(503, f"{self._what} is unavailable on this server right now ({self._reason}). "
                                 "Recorded investigations still work.")
