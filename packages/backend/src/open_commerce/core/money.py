"""Money value object and Decimal helpers."""

from decimal import ROUND_HALF_UP, Decimal

from pydantic import Field, field_validator

from open_commerce.core.types import StrictDomainModel


class Money(StrictDomainModel):
    """Money represented as integer minor units plus ISO-4217 currency."""

    amount_minor: int = Field(ge=0, strict=True)
    currency: str = Field(min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.upper()
        if not normalized.isalpha():
            raise ValueError("currency must be an ISO-4217 alphabetic code")
        return normalized

    def as_major_decimal(self, exponent: int = 2) -> Decimal:
        """Convert integer minor units to a Decimal major-unit amount."""

        return Decimal(self.amount_minor).scaleb(-exponent)

    def require_same_currency(self, other: "Money") -> None:
        """Raise when attempting to combine different currencies."""

        if self.currency != other.currency:
            raise ValueError("currency mismatch")

    def add(self, other: "Money") -> "Money":
        """Return the sum of two same-currency amounts."""

        self.require_same_currency(other)
        return Money(amount_minor=self.amount_minor + other.amount_minor, currency=self.currency)

    def subtract(self, other: "Money") -> "Money":
        """Return the non-negative difference of two same-currency amounts."""

        self.require_same_currency(other)
        result = self.amount_minor - other.amount_minor
        if result < 0:
            raise ValueError("money subtraction cannot produce a negative result")
        return Money(amount_minor=result, currency=self.currency)


def decimal_to_minor_units(value: Decimal, exponent: int = 2) -> int:
    """Round a Decimal major-unit amount to integer minor units."""

    scaled = value.scaleb(exponent).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(scaled)
