from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func

from database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    # No index= on the primary key: a PK already has its own (unique) index, so
    # an extra one is pure overhead.
    id = Column(Integer, primary_key=True)
    ticker = Column(String, unique=True, index=True, nullable=False)
    company_name = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    # timezone-aware, filled in by the database (server_default) so the value is
    # correct even for inserts that don't go through the ORM. Indexed because the
    # list endpoint orders by created_at DESC.
    created_at = Column(
        DateTime(timezone=True), index=True, nullable=False, server_default=func.now()
    )


class FinanceNote(Base):
    __tablename__ = "finance_notes"

    # No index= on the primary key (already indexed by the PK constraint).
    id = Column(Integer, primary_key=True)
    ticker = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JSON, default=list, nullable=False)
    source_url = Column(String, nullable=True)
    # Stable id supplied by an external source/agent; lets ingestion be
    # idempotent (re-sending the same external_id is skipped).
    external_id = Column(String(255), unique=True, index=True, nullable=True)
    created_at = Column(
        DateTime(timezone=True), index=True, nullable=False, server_default=func.now()
    )
