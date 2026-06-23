from typing import Annotated, Type, TypeVar

from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Query as SqlQuery, Session

from database import Base, get_db

# Inject a database session into a route with:  db: db_dependency
db_dependency = Annotated[Session, Depends(get_db)]

ModelT = TypeVar("ModelT", bound=Base)


def get_or_404(
    db: Session,
    model: Type[ModelT],
    item_id: int,
    detail: str = "Not found",
) -> ModelT:
    """Fetch a row by primary key or raise a 404. Replaces the repeated
    query/filter/first/None-check blocks across the routers."""
    obj = db.get(model, item_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=detail)
    return obj


class Pagination:
    """Reusable `?limit=&offset=` query parameters for list endpoints."""

    def __init__(
        self,
        limit: int = Query(50, ge=1, le=200, description="Max rows to return"),
        offset: int = Query(0, ge=0, description="Rows to skip"),
    ):
        self.limit = limit
        self.offset = offset


# Inject pagination into a route with:  page: PaginationParams
PaginationParams = Annotated[Pagination, Depends()]


def paginate(query: SqlQuery, page: Pagination) -> dict:
    """Run a list ``query`` as a single page and package it for a ``schemas.Page``
    response: the total row count (ignoring paging) plus the requested slice.

    Centralizing this means every list endpoint counts and slices identically.
    ``order_by(None)`` strips any ORDER BY for the COUNT (it's irrelevant there
    and keeps the SQL clean); the items query keeps whatever ordering the caller
    applied.
    """
    total = query.order_by(None).count()
    items = query.offset(page.offset).limit(page.limit).all()
    return {
        "items": items,
        "total": total,
        "limit": page.limit,
        "offset": page.offset,
    }
