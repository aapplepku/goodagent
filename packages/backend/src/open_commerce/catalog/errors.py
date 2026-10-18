"""Safe errors for provider-neutral catalog ingestion."""


class CatalogCSVError(ValueError):
    """A bounded catalog CSV could not be normalized safely."""
