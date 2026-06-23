import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from config import settings
from routers import financenotes, health, ingest, watchlist

logger = logging.getLogger("app")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend for tracking stock watchlist items and storing/searching "
        "finance notes, with idempotent bulk ingestion for automated agents."
    ),
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unexpected errors: log the full exception server-side and
    return a consistent, generic JSON body (matching FastAPI's ``{"detail": ...}``
    shape) instead of leaking a stack trace to the client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health.router)
app.include_router(watchlist.router)
app.include_router(financenotes.router)
app.include_router(ingest.router)
