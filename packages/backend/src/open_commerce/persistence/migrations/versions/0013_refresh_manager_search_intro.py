"""Refresh the exact legacy search-channel introduction.

Revision ID: 0013_refresh_search_intro
Revises: 0012_catalog_index_jobs
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_refresh_search_intro"
down_revision = "0012_catalog_index_jobs"
branch_labels = None
depends_on = None

_OLD_SEARCH_INTRO = (
    "This channel is for shopper search. Tell me what you want shoppers to find or how "
    "results should rank. I can turn that into a typed, reviewable objective; indexing and "
    "activation remain simulated until real data and tools are connected."
)
_NEW_SEARCH_INTRO = (
    "This channel is for shopper search. Tell me what you want shoppers to find or how "
    "results should rank. Catalog CSV uploads are indexed in the background and become "
    "searchable here once verified. Ranking changes remain review drafts until an activation "
    "tool is added."
)


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE manager_messages SET content = :new_content "
            "WHERE role = 'assistant' AND content = :old_content"
        ).bindparams(new_content=_NEW_SEARCH_INTRO, old_content=_OLD_SEARCH_INTRO)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE manager_messages SET content = :old_content "
            "WHERE role = 'assistant' AND content = :new_content"
        ).bindparams(old_content=_OLD_SEARCH_INTRO, new_content=_NEW_SEARCH_INTRO)
    )
