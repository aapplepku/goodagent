"""Public, provider-independent search failure categories."""


class SearchUnavailableError(RuntimeError):
    """The rebuildable retrieval dependency is unavailable."""


class SearchContextNotFoundError(LookupError):
    """The requested catalog context does not exist for this tenant."""


class SearchConstraintsError(ValueError):
    """Explicit shopper constraints are inconsistent."""
