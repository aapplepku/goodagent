"""Runtime diagnostics must not copy secrets, SQL or arbitrary exception messages."""

import json

from open_commerce.telemetry.diagnostics import exception_diagnostic


def test_exception_diagnostic_excludes_messages_and_values() -> None:
    try:
        try:
            raise ValueError("postgresql://private:secret@example.invalid/db")
        except ValueError as exc:
            raise RuntimeError("SELECT secret_value FROM customer") from exc
    except RuntimeError as error:
        diagnostic = exception_diagnostic(error)
    assert diagnostic["cause_types"] == ["RuntimeError", "ValueError"]
    encoded = json.dumps(diagnostic)
    assert not any(value in encoded for value in ("secret", "postgresql", "SELECT", "/Users/"))
