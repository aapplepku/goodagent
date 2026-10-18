"""bootstrap baseline."""

from collections.abc import Sequence

revision: str = "0001_bootstrap"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the empty baseline migration."""


def downgrade() -> None:
    """Revert the empty baseline migration."""
