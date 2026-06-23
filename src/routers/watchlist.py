from fastapi import APIRouter, HTTPException, Path
from sqlalchemy.exc import IntegrityError

import schemas
from deps import PaginationParams, db_dependency, get_or_404, paginate
from models import WatchlistItem

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

# Reusable OpenAPI response docs for this router's error cases.
NOT_FOUND = {404: {"description": "Watchlist item not found"}}
CONFLICT = {409: {"description": "Ticker already exists in watchlist"}}


@router.get("/", response_model=schemas.Page[schemas.WatchlistItemRead])
def read_watchlist(db: db_dependency, page: PaginationParams):
    query = db.query(WatchlistItem).order_by(WatchlistItem.created_at.desc())
    return paginate(query, page)


@router.get(
    "/{watchlist_item_id}",
    response_model=schemas.WatchlistItemRead,
    responses=NOT_FOUND,
)
def read_watchlist_item_by_id(db: db_dependency, watchlist_item_id: int = Path(gt=0)):
    return get_or_404(db, WatchlistItem, watchlist_item_id, "Watchlist item not found")


@router.post(
    "/",
    status_code=201,
    response_model=schemas.WatchlistItemRead,
    responses=CONFLICT,
)
def create_watchlist_item(
    db: db_dependency,
    watchlist_item_request: schemas.WatchlistItemCreate,
):
    watchlist_item = WatchlistItem(**watchlist_item_request.model_dump())
    db.add(watchlist_item)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Ticker already exists in watchlist",
        ) from exc

    db.refresh(watchlist_item)
    return watchlist_item


@router.put(
    "/{watchlist_item_id}",
    response_model=schemas.WatchlistItemRead,
    responses={**NOT_FOUND, **CONFLICT},
)
def update_watchlist_item(
    db: db_dependency,
    watchlist_item_request: schemas.WatchlistItemCreate,
    watchlist_item_id: int = Path(gt=0),
):
    watchlist_item = get_or_404(
        db, WatchlistItem, watchlist_item_id, "Watchlist item not found"
    )

    watchlist_item.ticker = watchlist_item_request.ticker
    watchlist_item.company_name = watchlist_item_request.company_name
    watchlist_item.notes = watchlist_item_request.notes

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Ticker already exists in watchlist",
        ) from exc

    db.refresh(watchlist_item)
    return watchlist_item


@router.delete("/{watchlist_item_id}", status_code=204, responses=NOT_FOUND)
def delete_watchlist_item(
    db: db_dependency,
    watchlist_item_id: int = Path(gt=0),
):
    watchlist_item = get_or_404(
        db, WatchlistItem, watchlist_item_id, "Watchlist item not found"
    )
    db.delete(watchlist_item)
    db.commit()
    # 204 No Content: no response body.
