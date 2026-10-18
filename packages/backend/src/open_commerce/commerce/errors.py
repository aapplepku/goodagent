"""Public commerce-domain errors with no transport dependencies."""


class CommerceNotFoundError(LookupError):
    """A tenant/account-scoped commerce object was not found."""


class CommerceConflictError(ValueError):
    """The requested operation conflicts with current cart or checkout state."""


class CommercePreconditionError(ValueError):
    """A price, stock, version, or reservation precondition is no longer true."""


class CommercePolicyDeniedError(ValueError):
    """The deterministic commerce policy rejected an operation."""
