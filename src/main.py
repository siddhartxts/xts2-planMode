from fastapi import FastAPI

from config import settings
from routers import financenotes, health, ingest, watchlist

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend for tracking stock watchlist items and storing/searching "
        "finance notes, with idempotent bulk ingestion for automated agents."
    ),
)


app.include_router(health.router)
app.include_router(watchlist.router)
app.include_router(financenotes.router)
app.include_router(ingest.router)
