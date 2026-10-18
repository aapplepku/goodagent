"""Central conservative redaction for structured and third-party log records."""

import re
from collections.abc import Mapping
from typing import cast
from uuid import UUID

from structlog.types import EventDict, WrappedLogger

REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "set_cookie",
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "client_secret",
    "private_key",
    "email",
    "phone",
    "phone_number",
    "address",
    "postal_address",
    "shipping_address",
    "billing_address",
    "first_name",
    "last_name",
    "customer_name",
    "customer",
    "prompt",
    "raw_prompt",
    "body",
    "payload",
    "headers",
    "exc_info",
    "stack_info",
}
_EMAIL = re.compile(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_CREDENTIAL_URL = re.compile(r"([a-z][a-z0-9+.-]*://)[^\s/@]+:[^\s/@]+@", re.I)
_BEARER = re.compile(r"\bBearer\s+[^\s,;\"']+", re.I)
_SECRET_PAIR = re.compile(
    r"\b(?:password|passwd|secret|token|access_token|refresh_token|api[_-]?key)"
    r"\s*[=:]\s*[^\s,;\"']+",
    re.I,
)
_PHONE = re.compile(r"(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)")
_TOKEN = re.compile(r"\b(?:sk-|ghp_|github_pat_|shpat_)[A-Za-z0-9_-]{8,}\b")


def redact_text(value: str) -> str:
    value = _CREDENTIAL_URL.sub(r"\1[REDACTED]@", value)
    value = _EMAIL.sub(REDACTED, value)
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _SECRET_PAIR.sub(REDACTED, value)
    value = _TOKEN.sub(REDACTED, value)
    return _PHONE.sub(
        lambda match: REDACTED if sum(char.isdigit() for char in match[0]) >= 10 else match[0],
        value,
    )[:4096]


def _request_uuid(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 36:
        return False
    try:
        parsed = UUID(value)
    except ValueError:
        return False
    return parsed.version == 4 and str(parsed) == value.lower()


def _redact(value: object, *, depth: int = 0) -> object:
    if depth > 8:
        return REDACTED
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in list(value.items())[:100]:
            label = str(key)
            normalized = label.lower().replace("-", "_")
            result[redact_text(label)] = (
                REDACTED
                if normalized in _SENSITIVE_KEYS
                or normalized.endswith(("_token", "_secret", "_password", "_email", "_phone"))
                else item
                if normalized == "request_id" and _request_uuid(item)
                else _redact(item, depth=depth + 1)
            )
        return result
    if isinstance(value, list | tuple | set):
        return [_redact(item, depth=depth + 1) for item in list(value)[:100]]
    if isinstance(value, str):
        return redact_text(value)
    if value is None or isinstance(value, bool | int | float):
        return value
    return f"<{type(value).__name__}>"


def redact_event(_: WrappedLogger, __: str, event: EventDict) -> EventDict:
    return cast(EventDict, _redact(event))
