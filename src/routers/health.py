from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from deps import db_dependency

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Liveness probe: the process is up and serving.

    Deliberately does NOT touch the database, so it stays green even while
    Postgres is unreachable. This is what the Docker/compose healthcheck calls.
    """
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(db: db_dependency):
    """Readiness probe: the app can actually do useful work, i.e. the database
    answers a trivial query.

    Returns 503 when the DB is unreachable so a load balancer / orchestrator can
    route around this instance instead of sending it traffic it can't serve.
    """
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}
