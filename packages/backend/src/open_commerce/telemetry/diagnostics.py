"""Allowlisted exception diagnostics without messages, SQL parameters or local values."""

from pathlib import Path
from traceback import extract_tb

from open_commerce.core.types import JsonObject


def exception_diagnostic(error: Exception) -> JsonObject:
    """Retain exception types and repository frame locations, never raw exception text."""
    frames: list[JsonObject] = []
    for frame in extract_tb(error.__traceback__):
        parts = Path(frame.filename).parts
        if "open_commerce" in parts:
            path = "/".join(parts[parts.index("open_commerce") :])
        elif "scripts" in parts:
            path = "/".join(parts[parts.index("scripts") :])
        else:
            continue
        frames.append({"file": path, "line": frame.lineno, "function": frame.name})
    causes: list[str] = []
    seen: set[int] = set()
    cause: BaseException | None = error
    while cause is not None and id(cause) not in seen and len(causes) < 8:
        seen.add(id(cause))
        causes.append(type(cause).__name__)
        cause = cause.__cause__ or cause.__context__
    return {"error": type(error).__name__, "cause_types": causes, "frames": frames}
