"""Safe shopper-agent failures surfaced by the API."""


class ShopperAuthenticationError(RuntimeError):
    """Credentials or session are invalid without revealing which field failed."""


class ShopperAccountConflictError(RuntimeError):
    """A shopper username already exists for the tenant."""


class ShopperConversationNotFoundError(RuntimeError):
    """Conversation does not belong to the authenticated shopper."""


class ShopperMemoryNotFoundError(RuntimeError):
    """Memory does not belong to the authenticated shopper."""


class ShopperUnsafeInputError(RuntimeError):
    """Input includes direct PII or credentials that cannot enter the agent context."""
