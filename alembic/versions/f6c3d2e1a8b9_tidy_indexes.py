"""tidy indexes: drop redundant PK indexes, index watchlist.created_at

- Drops ix_watchlist_id and ix_finance_notes_id: a primary key already has its
  own index, so these were pure overhead.
- Adds ix_watchlist_created_at: the watchlist list endpoint orders by
  created_at DESC, but the column was unindexed (finance_notes.created_at was
  already indexed by e5b2a1c4d6f7).

Revision ID: f6c3d2e1a8b9
Revises: e5b2a1c4d6f7
Create Date: 2026-06-23

"""

from alembic import op

revision = "f6c3d2e1a8b9"
down_revision = "e5b2a1c4d6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_watchlist_id", table_name="watchlist")
    op.drop_index("ix_finance_notes_id", table_name="finance_notes")
    op.create_index("ix_watchlist_created_at", "watchlist", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_watchlist_created_at", table_name="watchlist")
    op.create_index("ix_finance_notes_id", "finance_notes", ["id"])
    op.create_index("ix_watchlist_id", "watchlist", ["id"])
