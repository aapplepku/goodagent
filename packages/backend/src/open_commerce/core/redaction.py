"""Bounded redaction helpers for text entering hosted model context."""

import re

_SECRET_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?1[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\w)")
_ADDRESS_RE = re.compile(
    r"\b\d{1,6}\s+(?:[A-Za-z0-9.'-]+\s+){0,5}"
    r"(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr)\b\.?,?",
    re.IGNORECASE,
)
_NAMED_SECRET_RE = re.compile(
    r"\b(password|secret|access[_ -]?token|api[_ -]?key)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def redact_model_text(value: str) -> str:
    """Remove common credentials and direct contact PII before cloud model use."""

    redacted = _SECRET_RE.sub("[redacted-secret]", value)
    redacted = _NAMED_SECRET_RE.sub(lambda match: f"{match.group(1)}=[redacted]", redacted)
    redacted = _EMAIL_RE.sub("[redacted-email]", redacted)
    redacted = _PHONE_RE.sub("[redacted-phone]", redacted)
    return _ADDRESS_RE.sub("[redacted-address]", redacted)


def contains_direct_pii_or_secret(value: str) -> bool:
    """Return whether redaction would remove a credential or direct identifier."""

    return redact_model_text(value) != value


def redact_model_value(value: object) -> object:
    """Redact text leaves without altering numeric tool evidence or JSON structure."""
    if isinstance(value, str):
        return redact_model_text(value)
    if isinstance(value, list):
        return [redact_model_value(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_model_value(item) for key, item in value.items()}
    return value
