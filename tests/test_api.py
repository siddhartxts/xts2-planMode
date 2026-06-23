from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from database import get_db
from main import app


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready(client):
    # SQLite answers SELECT 1, so readiness passes.
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_health_ready_db_down(client):
    # Simulate an unreachable database: the SELECT 1 raises, readiness -> 503.
    class _BrokenSession:
        def execute(self, *args, **kwargs):
            raise SQLAlchemyError("database is down")

        def close(self):
            pass

    def broken_get_db():
        yield _BrokenSession()

    app.dependency_overrides[get_db] = broken_get_db  # cleared by the client fixture
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == "database unavailable"


def test_watchlist_crud(client):
    # create (ticker is normalized to upper-case)
    response = client.post(
        "/watchlist/", json={"ticker": "aapl", "company_name": "Apple"}
    )
    assert response.status_code == 201
    item = response.json()
    assert item["ticker"] == "AAPL"
    item_id = item["id"]

    # duplicate ticker -> 409
    assert client.post("/watchlist/", json={"ticker": "AAPL"}).status_code == 409

    # list (now a paginated envelope: items + total/limit/offset)
    listed = client.get("/watchlist/")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1

    # get by id / 404
    assert client.get(f"/watchlist/{item_id}").status_code == 200
    assert client.get("/watchlist/999999").status_code == 404

    # update
    updated = client.put(
        f"/watchlist/{item_id}", json={"ticker": "AAPL", "notes": "buy"}
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "buy"

    # delete -> 204 No Content, then gone
    assert client.delete(f"/watchlist/{item_id}").status_code == 204
    assert client.get(f"/watchlist/{item_id}").status_code == 404


def test_finance_notes_filter_and_pagination(client):
    client.post(
        "/financenotes/",
        json={"ticker": "AAPL", "title": "Earnings beat", "content": "iPhone sales"},
    )
    client.post(
        "/financenotes/",
        json={"ticker": "MSFT", "title": "Azure growth", "content": "Cloud revenue up"},
    )
    client.post(
        "/financenotes/",
        json={"ticker": "AAPL", "title": "Services", "content": "Margins improving"},
    )

    # filter by ticker (input is normalized to upper-case)
    by_ticker = client.get("/financenotes/", params={"ticker": "aapl"})
    assert by_ticker.status_code == 200
    assert by_ticker.json()["total"] == 2
    assert len(by_ticker.json()["items"]) == 2

    # full-text-ish search across title + content
    search = client.get("/financenotes/", params={"q": "azure"})
    assert search.json()["total"] == 1

    # pagination: limit caps the page, total still reflects all matches
    page = client.get("/financenotes/", params={"limit": 1}).json()
    assert len(page["items"]) == 1
    assert page["total"] == 3


def test_ingest_bulk_and_dedup(client):
    payload = [
        {"ticker": "AAPL", "title": "n1", "content": "c1", "external_id": "src-1"},
        {"ticker": "AAPL", "title": "n2", "content": "c2", "external_id": "src-2"},
    ]

    first = client.post("/ingest/finance-notes", json=payload)
    assert first.status_code == 200
    assert first.json()["created"] == 2
    assert first.json()["skipped"] == 0

    # re-sending the same external_ids is idempotent
    second = client.post("/ingest/finance-notes", json=payload).json()
    assert second["created"] == 0
    assert second["skipped"] == 2


def test_pagination_envelope(client):
    for ticker in ("AAA", "BBB", "CCC"):
        client.post(
            "/financenotes/",
            json={"ticker": ticker, "title": "t", "content": "c"},
        )

    body = client.get("/financenotes/", params={"limit": 2, "offset": 1}).json()
    assert body["total"] == 3  # total ignores limit/offset
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["items"]) == 2


def test_unhandled_error_returns_500_envelope(client):
    # An unexpected (non-HTTP) error should surface as a consistent 500 envelope,
    # not a leaked stack trace. Force readiness's SELECT 1 to raise a plain
    # RuntimeError (which the endpoint does NOT catch) to hit the app-wide
    # catch-all handler.
    class _Boom:
        def execute(self, *args, **kwargs):
            raise RuntimeError("boom")

        def close(self):
            pass

    def boom_get_db():
        yield _Boom()

    app.dependency_overrides[get_db] = boom_get_db  # cleared by the client fixture
    with TestClient(app, raise_server_exceptions=False) as boom_client:
        response = boom_client.get("/health/ready")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
