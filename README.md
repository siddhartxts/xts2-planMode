# Finance Watchlist & Notes Backend — A Learning Guide

> This README is written as a **teaching guide**, not a typical short GitHub readme.
> It walks a beginner through this exact codebase, slowly and in order. Every
> explanation is based on the code that is actually in this repository today.
> Where something is *not* built yet, this guide says so plainly.
>
> **The one thing to remember:** this project runs with **Docker Compose**.
> One command — `docker compose up --build` — starts the API, PostgreSQL, and a
> database GUI, and applies the migrations for you. You do **not** need to install
> Python, PostgreSQL, or the backend dependencies on your own machine to run it,
> and you should **not** start by running `uvicorn` by hand. A local Python setup
> exists only as an *optional* convenience for editor autocomplete and for advanced
> users — see [Optional: `.venv` for editor support](#11-optional-venv-for-editor-support)
> and [Optional / advanced: running without Docker](#12-optional--advanced-running-without-docker).

---

## Table of contents

1. [What this project is](#1-what-this-project-is)
2. [Big-picture mental model](#2-big-picture-mental-model)
3. [Recommended workflow — Docker Compose](#3-recommended-workflow--docker-compose)
4. [The Docker services](#4-the-docker-services)
5. [`db` vs `localhost`: the hostname rule](#5-db-vs-localhost-the-hostname-rule)
6. [Startup flow (what happens when you press "up")](#6-startup-flow)
7. [Migrations (Alembic), the Docker way](#7-migrations-alembic-the-docker-way)
8. [Testing, the Docker way](#8-testing-the-docker-way)
9. [API endpoints](#9-api-endpoints)
10. [The ingest endpoint](#10-the-ingest-endpoint)
11. [Optional: `.venv` for editor support](#11-optional-venv-for-editor-support)
12. [Optional / advanced: running without Docker](#12-optional--advanced-running-without-docker)
13. [Repository map](#13-repository-map)
14. [FastAPI explanation](#14-fastapi-explanation)
15. [Database and sessions](#15-database-and-sessions)
16. [Models vs. schemas](#16-models-vs-schemas)
17. [Common mistakes](#17-common-mistakes)
18. [What is intentionally not built yet](#18-what-is-intentionally-not-built-yet)
19. [Future roadmap](#19-future-roadmap)
20. [Quick command reference](#20-quick-command-reference)

---

## 1. What this project is

This is a small **backend API** for keeping track of stocks and writing notes
about them. It is a web server that other programs (a browser, a script, a future
mobile app, an automated agent) talk to over HTTP. It has no user interface of its
own beyond the automatic documentation page that FastAPI generates.

It manages two kinds of things:

- **Watchlist items** — a ticker symbol you want to follow (e.g. `AAPL`), with an
  optional company name and free-text notes.
- **Finance notes** — longer notes attached to a ticker: a title, a body of
  content, a list of tags, and an optional source URL.

### The problem it solves

If you research stocks, you accumulate scattered notes — a price target here, an
earnings summary there. This backend gives those notes **one structured home**
with a stable schema, so they can be created, searched, filtered, and (later)
analyzed programmatically instead of living in random text files.

### What it currently supports

- Full **CRUD** for **watchlist items** and **finance notes**.
- **Filtering and search** of notes by ticker, by a single tag, and by a text
  query that matches the title or content.
- **Pagination** on both list endpoints (`limit` / `offset`).
- A **bulk ingest** endpoint that accepts many notes at once and is *idempotent*
  (safe to re-send) when each note carries an `external_id`.
- A `/health` endpoint for monitoring.
- A fully **Dockerized** development stack (API + PostgreSQL + a database GUI).
- **Database migrations** managed by Alembic, applied automatically on startup.
- A small **test suite** that runs without needing a real database.

### What is staged for later (not built yet)

The schema is laid a little ahead of the features. The PostgreSQL **`pgvector`
extension is already enabled** by a migration, even though no embedding column
exists yet — groundwork for future *semantic search* (finding notes by meaning,
not just keywords). The `external_id` field on notes is groundwork for
**automated/agent ingestion**. There is **no authentication, no frontend, and no
production deployment setup** yet. See [section 18](#18-what-is-intentionally-not-built-yet)
for the honest list and [section 19](#19-future-roadmap) for the roadmap.

---

## 2. Big-picture mental model

Before any code, hold this picture in your head. A backend like this is a small
assembly line. A request comes in, passes through several stations, becomes a
database row, and a response comes back out.

The tools and their jobs:

| Tool | One-sentence job |
|------|------------------|
| **Docker Compose** | Runs the API, the database, and a DB admin GUI together as one stack. **This is how you run the project.** |
| **FastAPI** | Receives HTTP requests and routes them to Python functions. |
| **Pydantic** | Validates and cleans the JSON coming in, and shapes the JSON going out. |
| **SQLAlchemy** | Translates Python objects into SQL and talks to the database. |
| **PostgreSQL** | The actual database that stores the rows on disk. |
| **Alembic** | Versions and applies changes to the database's *structure* (tables/columns). |
| **entrypoint.sh** | Inside the API container: waits for the DB, runs migrations, then starts the server. |
| **uvicorn** | The web server process that runs the FastAPI app *inside the container*. You normally never invoke it by hand. |

The flow of a single request, top to bottom:

```
              HTTP request (JSON)
                     │
                     ▼
        ┌──────────────────────────┐
        │   uvicorn (web server)   │   listens on port 8000 (inside the container)
        └──────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │        FastAPI app       │   matches URL + method to a route function
        │       (src/main.py)      │
        └──────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │   Pydantic schema (in)   │   validates & cleans the request body
        │      (src/schemas.py)    │   e.g. "aapl" -> "AAPL"
        └──────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │   Router function        │   the business logic for this endpoint
        │  (src/routers/*.py)      │
        └──────────────────────────┘
                     │  uses a DB session (get_db)
                     ▼
        ┌──────────────────────────┐
        │   SQLAlchemy model       │   a Python object that maps to a table row
        │      (src/models.py)     │
        └──────────────────────────┘
                     │  SQLAlchemy turns it into SQL
                     ▼
        ┌──────────────────────────┐
        │       PostgreSQL         │   stores/reads the actual row (the "db" container)
        └──────────────────────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │  Pydantic schema (out)   │   turns the DB row back into clean JSON
        └──────────────────────────┘
                     │
                     ▼
              HTTP response (JSON)
```

And the surrounding infrastructure — the part you actually operate:

```
   docker compose up --build
          │
          ├── service: db        (PostgreSQL + pgvector, stores data on a volume)
          ├── service: api       (your FastAPI app; runs entrypoint.sh on boot)
          └── service: adminer   (a web GUI to inspect the database)

   entrypoint.sh (inside api):
      1. wait until db answers "SELECT 1"
      2. alembic upgrade head      ← builds/updates the tables
      3. exec uvicorn ...          ← starts serving requests
```

Keep returning to these two diagrams as you read the rest of the guide.

---

## 3. Recommended workflow — Docker Compose

**This is the normal, supported way to run the project.** Docker Compose starts
the API, PostgreSQL, and Adminer together, and runs the database migrations for
you on boot.

### What you need (and don't)

You need **Docker** with the **Docker Compose** plugin (`docker compose …`,
included in modern Docker Desktop / Docker Engine).

You do **not** need any of the following on your host machine to run the app:

- ❌ A local Python install or virtualenv.
- ❌ A local PostgreSQL server.
- ❌ The backend dependencies (`pip install …`).

All of that lives **inside the containers**. Your laptop only runs Docker.

### Step 1 — Create your `.env`

The compose file substitutes variables like `${API_PORT}` and
`${POSTGRES_PASSWORD}` from a file named `.env`. That file is gitignored, so you
create it from the committed template:

```bash
cp .env.example .env
```

Then open `.env` and set real values, in particular `POSTGRES_PASSWORD` and the
matching password inside `SQLALCHEMY_DATABASE_URL`. The template looks like this:

```env
# Host ports published by docker-compose (host:container)
API_PORT=8000
POSTGRES_PORT=5432
ADMINER_PORT=8080

# Postgres credentials (used by the db service)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-me
POSTGRES_DB=fastapi

# Connection string used by the api service and Alembic.
# Host is "db" (the compose service name) when running in Docker.
SQLALCHEMY_DATABASE_URL=postgresql://postgres:change-me@db:5432/fastapi
```

> **Two things to get right:**
> 1. If you change `POSTGRES_PASSWORD`, change the password inside
>    `SQLALCHEMY_DATABASE_URL` to match, or the API can't log into the database.
> 2. Leave the host as **`db`** in `SQLALCHEMY_DATABASE_URL`. That is the compose
>    service name, and it is what the API uses to reach Postgres *inside* Docker.
>    See [section 5](#5-db-vs-localhost-the-hostname-rule) for why it is `db` and
>    not `localhost`.

### Step 2 — Start the stack

```bash
docker compose up --build
```

- `docker compose up` — start all services defined in `docker-compose.yml`.
- `--build` — (re)build the API image first so your latest code is used. Use it
  whenever you've changed code or dependencies.

You'll see the database start, then the API container wait for it, run the
migrations, and finally print that uvicorn is serving. Leave this terminal open;
it streams the logs. (To run detached instead, use `docker compose up -d --build`
and follow logs separately — see [everyday commands](#everyday-commands).)

### Step 3 — Check it's alive

In another terminal:

```bash
curl http://localhost:8000/health
# -> {"status":"ok"}
```

(`8000` is your `API_PORT`. If you changed it in `.env`, use that port.)

### Step 4 — Explore the API in your browser

FastAPI generates interactive documentation automatically. Open:

- **http://localhost:8000/docs** — Swagger UI. Every endpoint is listed; you can
  fill in a body and click "Execute" to make real requests. This is the fastest
  way to learn the API.
- **http://localhost:8000/redoc** — an alternative, read-only documentation view.

### Step 5 — Inspect the database with Adminer

The stack includes **Adminer**, a small web GUI for the database. Open
**http://localhost:8080** (your `ADMINER_PORT`) and log in with:

- **System:** PostgreSQL
- **Server:** `db` (the service name; Adminer runs *inside* the Docker network)
- **Username / Password / Database:** the `POSTGRES_USER` / `POSTGRES_PASSWORD` /
  `POSTGRES_DB` from your `.env`.

You can browse tables, run SQL, and watch rows appear as you hit the API.

### Everyday commands

```bash
docker compose up --build        # build + start in the foreground (Ctrl-C to stop)
docker compose up -d --build     # build + start detached (runs in the background)
docker compose logs -f api       # follow the API container's logs
docker compose ps                # see which services are running
docker compose down              # stop and remove the containers (KEEPS data)
docker compose down -v           # stop AND delete the database volume (DESTROYS data)
```

> **`down` vs `down -v`:** plain `down` stops containers but keeps the named
> volume `postgres_data`, so your rows survive a restart. Adding `-v` deletes the
> volume — every row is gone and migrations run again from scratch on the next
> boot. Use `-v` only when you deliberately want a clean database.
>
> The `Makefile` provides short aliases for the Docker commands: `make up`,
> `make down`, `make logs`. Other `make` targets run on your *host* and belong to
> the optional/advanced workflow — see [section 12](#12-optional--advanced-running-without-docker).

---

## 4. The Docker services

If Docker is new to you: a **container** is an isolated mini-computer running one
process, built from an **image** (a frozen snapshot of an OS + code +
dependencies). Compose runs several containers together and lets them talk.

`docker-compose.yml` defines **three services**:

| Service (use this name with `docker compose exec`) | Container name | What it is | Published at (host) |
|---|---|---|---|
| **`api`** | `finance_backend_api` | The FastAPI app, built from the `Dockerfile`. Runs `entrypoint.sh` on boot. | `127.0.0.1:${API_PORT}` → container `8000` |
| **`db`** | `finance_backend_db` | PostgreSQL 16 with `pgvector` (`pgvector/pgvector:pg16`). Stores data on the `postgres_data` volume. | `127.0.0.1:${POSTGRES_PORT}` → container `5432` |
| **`adminer`** | `finance_backend_adminer` | A lightweight web GUI for the database. | `127.0.0.1:${ADMINER_PORT}` → container `8080` |

A few details worth understanding:

- **Why API and DB are separate.** The database is a stateful, long-lived store;
  the API is a stateless process you restart often as you change code. Keeping
  them in separate containers means you can rebuild and restart the API without
  disturbing the database.
- **Health checks and ordering.** The `db` service has a `pg_isready` health
  check, and `api` declares `depends_on: db (condition: service_healthy)`, so the
  API container only starts once Postgres is actually ready. The `api` service has
  its own health check that calls `/health` using Python (the slim image has no
  `curl`).
- **Ports are bound to `127.0.0.1`.** `"127.0.0.1:${API_PORT}:8000"` publishes the
  container's port `8000` to your machine *only* (not your whole network). The
  format is `host:container`.
- **The data volume.** PostgreSQL writes to `/var/lib/postgresql/data` inside its
  container; that path is mapped to the named volume `postgres_data`, so your data
  **survives** the container being recreated. `docker compose down -v` is what
  deletes it.
- **The image is lean on purpose.** The `Dockerfile` installs only
  `requirements.txt` (the runtime deps). The dev/test tools in
  `requirements-dev.txt` (`pytest`, `black`) are **not** baked into the image —
  this matters for [testing](#8-testing-the-docker-way).

---

## 5. `db` vs `localhost`: the hostname rule

This is the single most common source of "why can't it connect?" confusion, so it
gets its own section.

Compose creates a private network where each service is reachable by its **service
name** as a hostname. So:

- **Inside Docker** (e.g. from the `api` container, or from Adminer), the database
  is at **`db:5432`**. `db` is the service name.
- **From your host laptop** (outside Docker), the same database is at
  **`localhost:${POSTGRES_PORT}`**, because the port is published there.

That is exactly why the API's connection string uses `db`, not `localhost`:

```
postgresql://postgres:change-me@db:5432/fastapi
                                  ▲
                          the service name, not "localhost"
```

If you put `localhost` in the container's `SQLALCHEMY_DATABASE_URL`, the API tries
to connect to *itself* and fails. The only time you'd use `localhost` in that URL
is if you run the app **on your host** without Docker — the
[advanced workflow](#12-optional--advanced-running-without-docker).

---

## 6. Startup flow

When you run `docker compose up --build`, here is the timeline.

```
t0   You run: docker compose up --build
       │
t1   The "db" container starts PostgreSQL.
       │  Compose waits for db's healthcheck (pg_isready) to pass,
       │  because api declares: depends_on db (condition: service_healthy)
       ▼
t2   The "api" container starts and runs its CMD: sh /app/entrypoint.sh
       │
t3   entrypoint.sh step 1 — WAIT FOR POSTGRES
       │   A small Python loop tries "SELECT 1" up to 30 times, sleeping 1s
       │   between attempts, until Postgres answers.
       │   (Belt-and-suspenders even though Compose already waited.)
       ▼
t4   entrypoint.sh step 2 — RUN MIGRATIONS
       │   alembic upgrade head
       │   This creates/updates all tables to the latest schema version.
       ▼
t5   entrypoint.sh step 3 — START THE SERVER
       │   exec uvicorn main:app --app-dir src --host 0.0.0.0 --port 8000
       │   "exec" replaces the shell with uvicorn so signals work cleanly.
       ▼
t6   FastAPI is now serving on port 8000 inside the container,
       published to your machine at localhost:${API_PORT}.
       │
t7   The api healthcheck periodically calls /health. Once it returns 200,
       the api service is marked "healthy".
```

The key teaching point: **migrations run automatically at boot.** With Docker you
never have to remember to migrate — `entrypoint.sh` does it. (The `uvicorn` line
above is run *by the container*, not by you; this is the only place you should
think about uvicorn in the normal workflow.)

`entrypoint.sh` in essence:

```sh
set -e                          # stop on the first error
# 1. loop SELECT 1 until Postgres is reachable (30 tries)
# 2. alembic upgrade head
# 3. exec uvicorn main:app --app-dir src --host 0.0.0.0 --port 8000
```

---

## 7. Migrations (Alembic), the Docker way

### What migrations are, and why models alone aren't enough

Editing `src/models.py` changes your **Python description** of a table. It does
**not** change the actual PostgreSQL database — the real table on disk has no idea
you added a column. Something has to issue the `CREATE TABLE` / `ALTER TABLE` SQL
against the live database. That something is **Alembic**, and each change is
recorded as a **migration**: a small, ordered, version-controlled script.

> Mental model: `models.py` is the *blueprint*; migrations are the *construction
> work* that actually builds and remodels the database to match.

### You usually don't run anything — Docker does

As shown in [the startup flow](#6-startup-flow), `entrypoint.sh` runs
`alembic upgrade head` every time the `api` container boots. So when you
`docker compose up`, the database is brought to the latest schema automatically.

> **Single-instance caveat (worth knowing before you deploy).** Migrating from the
> container's entrypoint is safe here because there is exactly **one** `api`
> container. If you ever run **multiple** API replicas, they would all run
> `alembic upgrade head` at the same boot and could race each other. The
> production fix is to run migrations as a **separate deploy step** — one job that
> applies migrations *before* the app replicas start — not from each replica's
> entrypoint. For this single-host dev stack, the entrypoint approach is the right
> amount of machinery; revisit it when you move to multi-instance deployment.

### When you change a model: create and apply a migration in the container

Run Alembic **inside the `api` container**, because that container has the project
dependencies installed *and* the Docker-network access to reach the `db` service:

```bash
# 1. Generate a migration from the difference between your models and the DB:
docker compose exec api alembic revision --autogenerate -m "describe the change"

# 2. READ the generated file under alembic/versions/ — autogenerate is good, not perfect.

# 3. Apply it (also runs automatically on the next `up`, but you can do it now):
docker compose exec api alembic upgrade head
```

Other useful commands, same pattern:

```bash
docker compose exec api alembic current      # which revision is applied
docker compose exec api alembic history       # the full chain
docker compose exec api alembic downgrade -1  # undo the most recent migration
```

> **Why `docker compose exec api …`?** `exec` runs a command inside the
> already-running `api` container. Alembic needs both the installed Python packages
> and the correct `SQLALCHEMY_DATABASE_URL` (with host `db`) — both of which exist
> in that container and not necessarily on your host. Running Alembic on your host
> only makes sense in the [advanced no-Docker workflow](#12-optional--advanced-running-without-docker).
>
> **Note:** `alembic` *is* part of the runtime image (it's in `requirements.txt`),
> so these commands work out of the box — unlike `pytest`, see the next section.

### How Alembic finds your models, and the URL

`alembic/env.py` does `import models` and sets `target_metadata =
models.Base.metadata`, so autogenerate can diff your code against the live
database. It reads the database URL from the environment:

```python
database_url = os.getenv("SQLALCHEMY_DATABASE_URL") or config.get_main_option("sqlalchemy.url")
```

This is why `alembic.ini`'s `sqlalchemy.url` is intentionally left blank — the real
value comes from `SQLALCHEMY_DATABASE_URL`, which the `api` container already has.

### The `alembic_version` table

Alembic tracks which migrations have run via a tiny table called
**`alembic_version`** holding the current revision id. `upgrade head` runs only the
missing migrations, then updates that row. You can see it in Adminer.

### This repo's actual migration chain

Each migration points back to the previous via `down_revision`. Reading them in
order is a mini-history of the schema:

```
b79c8f92502b  create initial tables
                 └ creates "watchlist" and "finance_notes" with their indexes
                        │ down_revision = None  (this is the first migration)
                        ▼
2f4d8c6a9b10  add finance note ingest fields
                 └ adds finance_notes.tags (JSON) and finance_notes.source_url
                        ▼
c3e7f1a2b4d6  enable pgvector extension
                 └ op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                        ▼
d4a1f0b2c3e5  make created_at timezone-aware, non-null, db-defaulted
                 └ backfills NULLs, then alters both tables' created_at to
                   DateTime(timezone=True) NOT NULL DEFAULT now()
                        ▼
e5b2a1c4d6f7  add external_id and indexes   ◄── current head
                 └ adds finance_notes.external_id (unique) + index on created_at
```

Teaching points hidden in these files:

- **`d4a1f0b2c3e5`** shows real-world care: before adding `NOT NULL` it runs
  `UPDATE … SET created_at = now() WHERE created_at IS NULL` to backfill existing
  rows, and uses `postgresql_using="created_at AT TIME ZONE 'UTC'"` to reinterpret
  old naive timestamps as UTC. You can't just slap `NOT NULL` on a column that
  already has nulls.
- **`c3e7f1a2b4d6`** is how `pgvector` is "enabled": `CREATE EXTENSION IF NOT
  EXISTS vector` makes the `vector` type *available* — but **no table uses a vector
  column yet**. The capability is provisioned ahead of the feature.
- **`2f4d8c6a9b10`** adds `tags` with a temporary `server_default='[]'` so existing
  rows get a valid value, then drops the default so the application controls it
  going forward — the standard "add a non-null column to an existing table" trick.

---

## 8. Testing, the Docker way

### What the tests are

`pytest` discovers functions named `test_*`, runs them, and reports pass/fail.
`pytest.ini` sets `testpaths = tests` and `pythonpath = src` so a test can simply
`from main import app`.

The clever part is in `tests/conftest.py`: the `client` fixture spins up an
**in-memory SQLite** database per test, creates the tables with
`Base.metadata.create_all(...)`, and **overrides** the real `get_db` dependency to
use that SQLite session. So **the tests need no PostgreSQL and no running stack** —
they execute entirely in-process via FastAPI's `TestClient`.

### Important: the runtime image does not include pytest

The `Dockerfile` installs only `requirements.txt`. The test tools (`pytest`,
`black`) live in `requirements-dev.txt` and are **deliberately kept out of the
image** to keep it lean. So `docker compose exec api pytest` will fail with
"command not found" *unless you first install the dev dependencies into the running
container.*

### Running the tests inside the container

With the stack up (`docker compose up -d --build`), install the dev tools into the
running `api` container, then run pytest:

```bash
docker compose exec api pip install -r requirements-dev.txt   # one-time per running container
docker compose exec api pytest                                # run the whole suite
docker compose exec api python -m pytest                      # equivalent
docker compose exec api pytest tests/test_api.py::test_watchlist_crud   # a single test
```

> **Heads up:** those `pip install`ed dev tools live only in the *current* running
> container. If you rebuild or recreate it (`docker compose up --build`, or `down`
> then `up`), you'll need to install them again. That's the trade-off for a lean
> image. If you run tests often, the [optional `.venv`](#11-optional-venv-for-editor-support)
> on your host is usually more convenient for this one task.

### What the current tests check

In `tests/test_api.py`:

- **`test_health`** — `/health` returns `200` and `{"status": "ok"}`.
- **`test_watchlist_crud`** — the full lifecycle: create (and that `"aapl"` is
  normalized to `"AAPL"`), duplicate → `409`, list, get-by-id, `404` for a missing
  id, update, delete, then `404` again.
- **`test_finance_notes_filter_and_pagination`** — creates three notes, then checks
  filtering by ticker, the `q` text search, and the `limit` pagination.
- **`test_ingest_bulk_and_dedup`** — posts a batch (expects `created=2`), then posts
  the *same* batch again and expects `created=0, skipped=2` — proving idempotency.

### What a passing test does and doesn't prove

It means the endpoints behaved correctly against in-memory SQLite for the written
scenarios. It does **not** prove the Postgres-only paths work — in particular the
**`tag` filter uses a PostgreSQL JSONB operator that SQLite can't run**, so it is
not exercised by these tests — nor does it run the Alembic migrations (the tests
build tables straight from the models with `create_all`).

### Good tests to add next

- The **`tag` filter** against a real Postgres (e.g. a test container).
- Validation tests: missing `ticker` → `422`, bad `source_url` → `422`.
- An ingest test mixing notes **with and without** `external_id` in one batch.
- A test that runs the **migrations** against a fresh database and asserts the
  resulting schema.

---

## 9. API endpoints

Below is every endpoint currently implemented. All examples assume the API is at
`http://localhost:8000` (your `API_PORT`).

> **Note on the `tag` filter:** filtering notes by tag uses a PostgreSQL-specific
> JSONB operator, so it works against the real Postgres database but is **not**
> exercised by the SQLite-based tests.

### `GET /health` — liveness check
- **File:** `src/routers/health.py` · **Table touched:** none — returns
  `{"status": "ok"}`. Answers "is the process up?" *without* touching the
  database, so it stays green even when Postgres is down. This is what the Docker
  healthcheck calls.

```bash
curl http://localhost:8000/health
```

### `GET /health/ready` — readiness check
- **File:** `src/routers/health.py` · **Table touched:** runs `SELECT 1`.
  Answers "can the app actually serve traffic?" Returns `200 {"status": "ready"}`
  when the database answers, or **`503`** when it is unreachable — what a load
  balancer / orchestrator should poll before routing traffic to this instance.

```bash
curl -i http://localhost:8000/health/ready
```

### Watchlist — `src/routers/watchlist.py` (table: `watchlist`)

**`GET /watchlist/`** — list items, newest first, paginated.
- Query params: `limit` (1–200, default 50), `offset` (≥0, default 0).
```bash
curl "http://localhost:8000/watchlist/?limit=10&offset=0"
```

**`GET /watchlist/{id}`** — fetch one item by id (404 if missing).
```bash
curl http://localhost:8000/watchlist/1
```

**`POST /watchlist/`** — create an item. Returns `201`. Duplicate ticker → `409`.
- Body:
```json
{ "ticker": "aapl", "company_name": "Apple", "notes": "core holding" }
```
- Response (`201`):
```json
{ "ticker": "AAPL", "company_name": "Apple", "notes": "core holding",
  "id": 1, "created_at": "2026-06-22T12:00:00+00:00" }
```
```bash
curl -X POST http://localhost:8000/watchlist/ \
  -H "Content-Type: application/json" \
  -d '{"ticker":"aapl","company_name":"Apple"}'
```

**`PUT /watchlist/{id}`** — replace an item's fields (404 if missing, 409 on ticker
clash).
```bash
curl -X PUT http://localhost:8000/watchlist/1 \
  -H "Content-Type: application/json" \
  -d '{"ticker":"AAPL","notes":"trim position"}'
```

**`DELETE /watchlist/{id}`** — delete an item (404 if missing).
```bash
curl -X DELETE http://localhost:8000/watchlist/1
# -> {"message":"Watchlist item deleted successfully"}
```

### Finance notes — `src/routers/financenotes.py` (table: `finance_notes`)

**`GET /financenotes/`** — list notes, newest first, paginated, with optional
filters:
- `ticker` — exact match (input is upper-cased).
- `q` — case-insensitive search across `title` and `content`.
- `tag` — match notes containing this tag (**Postgres-only**).
- `limit` / `offset` — pagination.
```bash
curl "http://localhost:8000/financenotes/?ticker=aapl&q=earnings&limit=20"
```

**`GET /financenotes/{id}`** — fetch one note by id (404 if missing).

**`POST /financenotes/`** — create a note. Returns `201`.
- Body:
```json
{ "ticker": "AAPL", "title": "Q3 earnings beat",
  "content": "Revenue up on iPhone + Services.",
  "tags": ["earnings", "bullish"],
  "source_url": "https://example.com/report" }
```
```bash
curl -X POST http://localhost:8000/financenotes/ \
  -H "Content-Type: application/json" \
  -d '{"ticker":"AAPL","title":"Q3 earnings beat","content":"Revenue up."}'
```

**`PUT /financenotes/{id}`** — replace a note's fields (404 if missing).

**`DELETE /financenotes/{id}`** — delete a note (404 if missing).

### Ingest — `src/routers/ingest.py` (table: `finance_notes`)

**`POST /ingest/finance-notes`** — bulk-create notes idempotently. Returns `200`
with a summary. Covered in detail in the [next section](#10-the-ingest-endpoint).
```bash
curl -X POST http://localhost:8000/ingest/finance-notes \
  -H "Content-Type: application/json" \
  -d '[{"ticker":"AAPL","title":"n1","content":"c1","external_id":"src-1"},
       {"ticker":"MSFT","title":"n2","content":"c2","external_id":"src-2"}]'
# -> {"created":2,"skipped":0,"items":[ ... ]}
```

---

## 10. The ingest endpoint

### What it currently does

`POST /ingest/finance-notes` takes a **list** of notes (not a single one) and
inserts them, returning a summary: how many were `created`, how many `skipped`, and
the created `items`.

Its defining feature is **idempotency via `external_id`**:

```python
for note in notes:
    if note.external_id:
        already_exists = db.query(FinanceNote).filter(
            FinanceNote.external_id == note.external_id).first()
        if already_exists:
            skipped += 1
            continue

    finance_note = FinanceNote(**note.model_dump())
    db.add(finance_note)
    try:
        db.commit()
    except IntegrityError:   # e.g. a concurrent insert of the same external_id
        db.rollback()
        skipped += 1
        continue
    db.refresh(finance_note)
    created.append(finance_note)
```

Two robustness choices to learn from:

1. **One commit per note**, not one big commit for the whole batch. If a single
   note fails, the others still go through — the batch isn't all-or-nothing.
2. **Defense in depth on uniqueness.** It checks for an existing `external_id`
   first, *and* catches the database's `IntegrityError` in case two requests race
   to insert the same id. The unique index on `external_id` (migration
   `e5b2a1c4d6f7`) is the ultimate guarantee.

### Why it exists

A normal `POST /financenotes/` is for a human creating one note. The ingest
endpoint is for **bulk, repeatable, machine-driven** loading where the caller may
send the same data more than once (retries, scheduled re-runs, overlapping
batches). The `external_id` is the sender's own stable identifier for each note;
using it as a dedup key means re-sending a batch is safe and produces no
duplicates.

### Normal CRUD vs. machine/agent ingest

| | User CRUD (`POST /financenotes/`) | Machine ingest (`POST /ingest/finance-notes`) |
|---|---|---|
| Input | one note | a list of notes |
| Caller | a human via UI/docs | a script or agent |
| Re-sending | creates a duplicate | skipped (idempotent) |
| Dedup key | none | `external_id` |
| Response | the created note | a `{created, skipped, items}` summary |

An automated agent (the roadmap nicknames this "OpenClaw") would give each note it
produces a deterministic `external_id` (say, a hash of the source URL) and POST its
whole batch on a schedule without tracking what it already sent — the backend skips
anything it's seen.

---

## 11. Optional: `.venv` for editor support

> **This is optional and is *not* how you run the app.** Everything above runs the
> backend entirely in Docker. A local virtualenv exists only to make your **editor**
> smarter. Skip this section if you just want to run the project.

When you open `src/` in VS Code (or another editor) *without* the packages
installed locally, Pylance/Python can't resolve `from fastapi import …`,
`from models import …`, etc., and you get yellow squiggly "unresolved import"
warnings. A local `.venv` with the dependencies installed fixes that — purely for
the editor.

### Create it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Then point your editor at `.venv` as its Python interpreter (in VS Code:
*Python: Select Interpreter* → choose `./.venv`).

### What this gives you

- **Import resolution** — no more "unresolved import" squiggles.
- **Autocomplete** and inline type hints.
- **Linting / formatting** hooks in the editor (`black`).
- **Test discovery** — your editor's test panel can find and run the `tests/`.

### What it is *not*

- It is **not required** for Docker Compose to run the backend. The app runs from
  the dependencies inside the `api` container, not from `.venv`.
- It does **not replace** the container environment. Code actually executes in the
  container; `.venv` is just a mirror your editor reads for IntelliSense.
- It should **not be committed.** `.gitignore` already excludes `.venv/`.

> **Tip on the flat-import layout:** the app runs with `--app-dir src`, so imports
> inside `src/` are top-level (`from models import …`, not `from src.models import …`).
> For your editor to resolve those, add `src` to its analysis path (VS Code:
> set `"python.analysis.extraPaths": ["src"]`). `pytest` already handles this via
> `pythonpath = src` in `pytest.ini`.

---

## 12. Optional / advanced: running without Docker

> **This is not the normal workflow.** It exists for advanced users who want
> host-side autoreload. For everyone else, Docker Compose
> ([section 3](#3-recommended-workflow--docker-compose)) is simpler, more
> consistent, and is what this repo is built around. If you're a beginner, use
> Docker and ignore this section.

Running the API directly on your host with `uvicorn` means **you** take over the
jobs that Docker normally does for you, and you must get all of these right:

1. **Install the dependencies locally** (ideally in a virtualenv):
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements-dev.txt    # pulls in requirements.txt too
   ```
2. **Provide a PostgreSQL the host can reach.** You need a running Postgres and a
   `SQLALCHEMY_DATABASE_URL` that uses **`localhost`** (not `db`), e.g.
   `postgresql://postgres:change-me@localhost:5432/fastapi`. A common pattern is to
   run *only* the database in Docker and point the host app at it:
   ```bash
   docker compose up -d db          # start just Postgres, published on localhost:${POSTGRES_PORT}
   ```
   (Remember: from the host the DB is `localhost`, per [section 5](#5-db-vs-localhost-the-hostname-rule).)
3. **Run the migrations yourself** — there is no `entrypoint.sh` doing it for you:
   ```bash
   alembic upgrade head
   ```
4. **Start the server** with autoreload:
   ```bash
   uvicorn main:app --app-dir src --reload
   ```

The `Makefile` bundles these host-side steps as conveniences — but note they all
run on your **host**, not in Docker, and depend on the setup above:

| `make` target | Runs (on the host) | Notes |
|---|---|---|
| `make install` | `pip install -r requirements-dev.txt` | local deps for editor/tests/advanced run |
| `make dev` | `uvicorn main:app --app-dir src --reload` | the advanced host run; needs a reachable Postgres |
| `make migrate` | `alembic upgrade head` | host-side migrate (Docker does this automatically) |
| `make revision m="…"` | `alembic revision --autogenerate -m "…"` | host-side migration generate |
| `make test` | `pytest` | host-side tests; needs dev deps installed |
| `make fmt` | `black src alembic tests` | format the code |
| `make up` / `make down` / `make logs` | the Docker commands | **these are the recommended ones** |

If anything here feels fiddly, that's the point: Docker exists so you don't have to
do steps 1–4 by hand. Prefer `docker compose up --build`.

---

## 13. Repository map

Every important file, what it is, and when *you* would touch it.

### Infrastructure & configuration

- **`docker-compose.yml`** — the three services (`api`, `db`, `adminer`), their
  ports, health checks, and the data volume. **Touch it** to add a service or
  change wiring.
- **`Dockerfile`** — the recipe for the API image: Python 3.14-slim, install
  `requirements.txt`, copy the code, define the startup command. Note it does
  **not** install `requirements-dev.txt`. **Touch it** when the build changes.
- **`entrypoint.sh`** — what the API container runs on boot: wait for Postgres,
  `alembic upgrade head`, then `exec uvicorn`. **Touch it** to change startup.
- **`.dockerignore`** — what Docker must *not* copy into the image: the host
  `.venv` (wrong-arch binaries), caches, `.git/`, `.env`, even the docs. **Touch
  it** to keep large/secret files out of the image.
- **`.env.example`** — the committed template of required variables (ports, DB
  credentials, the DB URL). Copy it to `.env` before running. **Touch it** when you
  add a new config value.
- **`.gitignore`** — ignores `.env`/`.env.*` (keeps `!.env.example`), caches, and
  `.venv/`. **Touch it** rarely.
- **`requirements.txt`** — **runtime** deps (FastAPI, SQLAlchemy, Alembic, the
  Postgres driver). These go into the image.
- **`requirements-dev.txt`** — **dev/test** tools (`pytest`, `pytest-asyncio`,
  `black`); pulls in `requirements.txt` via `-r`. Kept *out* of the image.
- **`Makefile`** — short aliases. Docker ones (`up`/`down`/`logs`) are the
  recommended ones; the rest run on the host (see [section 12](#12-optional--advanced-running-without-docker)).
- **`pytest.ini`** — `pythonpath = src` (so tests can `import main`) and
  `testpaths = tests`.
- **`alembic.ini`** — Alembic config; its `sqlalchemy.url` is intentionally blank
  (the URL comes from `SQLALCHEMY_DATABASE_URL`).

### Migrations — `alembic/`

- `alembic/env.py` — reads `SQLALCHEMY_DATABASE_URL` and points Alembic at
  `models.Base.metadata` for autogeneration.
- `alembic/versions/*.py` — the ordered migration files (the chain in
  [section 7](#7-migrations-alembic-the-docker-way)). **Touch this folder** every
  time you change a model.
- `alembic/script.py.mako`, `alembic/README` — the migration template and a stock
  note.

### Application source — `src/`

The app uses a **flat import layout**: it runs with `--app-dir src`, so files say
`from models import …` and `from routers import …`, *not* `from src.models import …`.

- **`src/main.py`** — creates the FastAPI app (title/version from `settings`) and
  wires in the routers (`health`, `watchlist`, `financenotes`, `ingest`).
- **`src/database.py`** — the SQLAlchemy engine, `SessionLocal`, the `Base`, and the
  `get_db` dependency.
- **`src/config.py`** — a Pydantic-Settings class. `SQLALCHEMY_DATABASE_URL` is
  **required** (no default — the app fails fast at startup if it's missing instead
  of silently connecting somewhere); it also holds `environment`, `log_level`, and
  the `app_name`/`app_version` shown on the `/docs` page.
- **`src/models.py`** — the SQLAlchemy models `WatchlistItem` and `FinanceNote` (the
  database *tables*).
- **`src/schemas.py`** — the Pydantic schemas (request/response shapes + validators).
- **`src/deps.py`** — shared dependencies: `db_dependency`, `get_or_404`, and the
  `Pagination` (`limit`/`offset`) params.
- **`src/routers/`** — `health.py` (`/health` liveness + `/health/ready`
  readiness), `watchlist.py` (CRUD), `financenotes.py` (CRUD + search),
  `ingest.py` (bulk idempotent ingest), and an empty `__init__.py`.

### Tests — `tests/`

- **`tests/conftest.py`** — the `client` fixture backed by in-memory SQLite, with
  `get_db` overridden. No Postgres needed.
- **`tests/test_api.py`** — health, watchlist CRUD, note filtering/pagination, and
  ingest dedup.

### Other

- **`CLAUDE.md`** — notes for the Claude Code AI assistant about this repo's
  conventions. Not required to run anything.

---

## 14. FastAPI explanation

FastAPI turns Python functions into HTTP endpoints. `src/main.py` is intentionally
tiny:

```python
from fastapi import FastAPI

from config import settings
from routers import financenotes, health, ingest, watchlist

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="...",
)

app.include_router(health.router)
app.include_router(watchlist.router)
app.include_router(financenotes.router)
app.include_router(ingest.router)
```

- `app = FastAPI(title=..., version=...)` creates the application object; the
  title/version come from `config.settings`, so the auto-generated `/docs` page is
  labelled with the app's name and version. This `app` is what uvicorn runs inside
  the container (`uvicorn main:app`).
- `app.include_router(...)` plugs in each **router** — a group of related endpoints
  in its own file with a shared URL prefix (`/health`, `/watchlist`,
  `/financenotes`, `/ingest`). This keeps `main.py` small; even the health
  endpoints live in their own `src/routers/health.py`.

**`/health`** returns `200 OK` without touching the database — the Docker health
check calls it to ask "are you alive?" (**liveness**). Its sibling
**`/health/ready`** *does* ping the database (`SELECT 1`) and returns `503` when it
can't, answering "can you serve traffic?" (**readiness**). Keeping the two
separate is a standard production pattern: a process can be alive but not yet
ready (e.g. the DB is still starting).

**`/docs`** (Swagger UI) and **`/redoc`** (ReDoc) are generated automatically from
your routes and Pydantic schemas. You didn't write those pages; they're derived
from the code, so they can never drift from it.

How a request reaches a route function:

1. uvicorn receives the raw HTTP request.
2. FastAPI matches the **method + path** (e.g. `POST /watchlist/`) to a route.
3. FastAPI resolves the function's **dependencies** (a DB session, a validated
   body) and calls it.
4. The function returns a value; FastAPI serializes it (often via a
   `response_model`) into JSON.

Step 3 — dependencies — is how the database session and request validation get
injected, which the next sections explain.

---

## 15. Database and sessions

PostgreSQL is a separate server program (the `db` container) that stores rows
durably and answers SQL. The API never reads files directly — it asks Postgres over
a connection.

`src/database.py`, in essence:

```python
from config import settings

engine = create_engine(settings.sqlalchemy_database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- **`engine`** — knows *how* to connect (the URL, the connection pool). One per app.
- **`SessionLocal`** — a factory of `Session` objects. A **session** is your
  workspace for one unit of work. `autocommit=False` means changes aren't saved
  until you `commit()`.
- **`Base`** — the declarative base every model inherits from; `Base.metadata`
  collects the table definitions Alembic uses.
- **`get_db`** — a FastAPI **dependency** that hands a session to a request and
  guarantees it's closed.

**Why `yield db`:** `get_db` is a generator. FastAPI runs it up to the `yield`,
hands the `db` to your route, and after the response resumes it *past* the `yield`
so `finally: db.close()` runs. That gives **one fresh session per request** with no
leaked connections, even if the route raises.

In `deps.py` the session is packaged so routes can request it cleanly:

```python
db_dependency = Annotated[Session, Depends(get_db)]
```

A route then writes `db: db_dependency` and FastAPI injects a live session.
`deps.py` also provides `get_or_404(db, model, item_id, detail)` — a primary-key
lookup that raises `HTTPException(404)` when the row is missing, replacing a block
repeated across every get/update/delete route.

---

## 16. Models vs. schemas

This is the single most important concept in the codebase, and a classic point of
confusion: **two different kinds of classes that look similar but do different
jobs.**

### SQLAlchemy models = database tables

`src/models.py` defines what the **tables** look like. Each class is a table; each
`Column` is a column.

```python
class WatchlistItem(Base):
    __tablename__ = "watchlist"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True, nullable=False)
    company_name = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now())
```

Details that encode real rules:

- `ticker` is `unique=True` — the database itself refuses two rows with the same
  ticker. (That's what lets the route translate a clash into HTTP 409.)
- `created_at` uses `server_default=func.now()` — **the database** fills in the
  timestamp.

`FinanceNote` adds `tags` (a `JSON` column defaulting to `[]`), `source_url`, and
`external_id` (`unique`, nullable) — the last enabling idempotent ingestion.

### Pydantic schemas = request/response shapes

`src/schemas.py` defines what the **JSON going in and out** looks like, and
validates it. These never touch SQL.

```python
class WatchlistItemBase(BaseModel):
    ticker: str
    company_name: str | None = None
    notes: str | None = None

    @field_validator("ticker")
    @classmethod
    def clean_ticker(cls, value: str) -> str:
        ticker = value.strip().upper()      # "  aapl " -> "AAPL"
        if not ticker:
            raise ValueError("ticker is required")
        return ticker
```

The schemas come in deliberate variants:

- **`...Base`** — shared fields and validators.
- **`...Create`** — what a client must send to create something.
- **`...Read`** — what the API returns (adds DB-generated `id`, `created_at`). It
  sets `model_config = ConfigDict(from_attributes=True)`, which lets Pydantic build
  the response *directly from a SQLAlchemy model object*.
- **`...Ingest`** — like Create but with the optional `external_id`.

The `FinanceNote` schemas also clean input: `tags` can arrive as a list *or* a
comma-separated string and is normalized to a list; `source_url` must start with
`http://` or `https://` or it's rejected.

### Why both are needed

The **model** is about *storage* (types, constraints, indexes). The **schema** is
about the *contract and validation* (what callers may send/receive, how messy input
is cleaned). Separating them means you can change the API's shape without changing
the table, and you never accidentally expose internal columns or accept
unvalidated junk.

### Following one request all the way through

`POST /watchlist/` with body `{"ticker": "aapl", "company_name": "Apple"}`:

```
1. HTTP arrives:  POST /watchlist/  body = {"ticker":"aapl","company_name":"Apple"}

2. FastAPI parses the JSON into schemas.WatchlistItemCreate; the validator runs:
        "aapl" -> strip + upper -> "AAPL"

3. The route (src/routers/watchlist.py) runs:
        watchlist_item = WatchlistItem(**request.model_dump())
        db.add(watchlist_item)
        db.commit()           -> INSERT INTO watchlist (...) VALUES ('AAPL', 'Apple', ...)
                                 Postgres fills created_at via server_default now()
        db.refresh(watchlist_item)   -> reloads id and created_at from the row

4. The route returns the model; response_model=schemas.WatchlistItemRead with
   from_attributes=True builds:
        {"ticker":"AAPL","company_name":"Apple","notes":null,
         "id":1,"created_at":"2026-06-22T..."}

5. FastAPI sends that JSON back with status 201.
```

If you sent a duplicate `AAPL`, step 3's `commit()` raises `IntegrityError` (the
unique constraint); the route catches it, rolls back, and raises
`HTTPException(409, "Ticker already exists in watchlist")`.

---

## 17. Common mistakes

The specific traps this stack sets, and how to avoid them.

- **Trying to run it without Docker first.** The supported path is
  `docker compose up --build`. Reaching for host `uvicorn`/`pip` as a beginner is
  the [advanced workflow](#12-optional--advanced-running-without-docker) and adds
  several ways to get stuck. Use Docker.

- **Forgetting to copy `.env.example` to `.env`.** Compose can't substitute
  `${API_PORT}`/`${POSTGRES_PASSWORD}` and the stack won't start. Always
  `cp .env.example .env` first.

- **Confusing `localhost` and `db` as the database host.** Inside Docker the
  database is `db:5432`; from your host it's `localhost:${POSTGRES_PORT}`. Putting
  `localhost` in the container's `SQLALCHEMY_DATABASE_URL` makes the API try to
  connect to *itself*. See [section 5](#5-db-vs-localhost-the-hostname-rule).

- **Expecting `docker compose exec api pytest` to work out of the box.** The image
  doesn't include `pytest`/`black`. Install dev deps into the container first, or
  use the host `.venv`. See [section 8](#8-testing-the-docker-way).

- **Deleting the volume and losing data.** `docker compose down -v` erases
  `postgres_data`. Use plain `down` unless you *want* a clean database.

- **Port already in use.** If `8000`, `5432`, or `8080` is taken (e.g. a local
  Postgres already on `5432`), the stack fails to bind. Change the offending
  `*_PORT` in `.env`.

- **Docker running old code.** If a change doesn't take effect, you probably
  started without rebuilding. Use `docker compose up --build`.

- **Committing `.env`.** It holds secrets and is gitignored on purpose. Only
  `.env.example` (placeholders) belongs in Git.

- **Changing a model but not creating a migration.** Editing `models.py` does
  nothing to the live database. Generate and apply a migration —
  `docker compose exec api alembic revision --autogenerate -m "…"` then
  `… alembic upgrade head` (or just restart the stack). Code and database must move
  together.

- **Expecting SQLAlchemy to auto-update tables.** It does not alter existing tables
  to match the models — that's Alembic's job. (The only auto-create-from-models is
  in the **tests**, on a throwaway SQLite DB.)

- **Import-path confusion from `--app-dir src`.** Imports inside `src/` are flat
  (`from models import …`, not `from src.models import …`). New modules must follow
  this, and your editor needs `src` on its analysis path (see
  [section 11](#11-optional-venv-for-editor-support)).

---

## 18. What is intentionally not built yet

Being honest about the boundaries is part of the lesson.

- **No authentication or authorization.** No login, no JWT, no API keys; every
  endpoint is open. (`bcrypt`, `passlib`, `python-jose` are present in
  `requirements.txt` as groundwork, but nothing uses them yet.)
- **No frontend.** Only the JSON API and the auto-generated `/docs`.
- **No production deployment setup.** The Docker stack is for *development* — no
  HTTPS, no reverse proxy, no production process manager, no cloud config.
- **No Kubernetes / orchestration.** Single-host Docker Compose only.
- **No semantic search yet.** `pgvector` is enabled, but there is no embedding
  column on any table and no vector-search endpoint. The capability is staged, not
  built.
- **No real external finance data.** Nothing fetches live prices or news; you put
  the data in yourself.

---

## 19. Future roadmap

Roughly in the order they follow from what's here:

- **Richer note querying** — multi-tag matching, date ranges, combined search.
- **Better tagging** — a controlled vocabulary or a separate tags table instead of
  a free-form JSON list.
- **Agent / "OpenClaw" ingestion** — build the automated producer that posts
  batches to `/ingest/finance-notes` using deterministic `external_id`s.
- **pgvector semantic search** — add an embedding column to `finance_notes`, store
  vector embeddings, and add a "search by meaning" endpoint. The extension is
  already enabled, so this is the natural payoff.
- **Authentication** — wire up the already-present `passlib`/`bcrypt`/`python-jose`
  into real login and protected routes.
- **More tests** — Postgres-backed tests for the JSONB tag filter, validation-error
  tests, and tests that run the migrations against a real database.

---

## 20. Quick command reference

```bash
# --- Setup (once) ---
cp .env.example .env             # create your local env file, then edit secrets

# --- Run with Docker Compose (THE NORMAL WORKFLOW) ---
docker compose up --build        # build + start API + db + adminer, run migrations
docker compose up -d --build     # same, detached (background)
docker compose logs -f api       # follow the API logs   (alias: make logs)
docker compose ps                # list running services
docker compose down              # stop, KEEP data        (alias: make down)
docker compose down -v           # stop, DELETE the DB volume (destroys data)

# --- Health, docs, DB GUI (with the stack up) ---
curl http://localhost:8000/health   # liveness check
# http://localhost:8000/docs        # interactive API docs (Swagger UI)
# http://localhost:8000/redoc       # alternative docs (ReDoc)
# http://localhost:8080             # Adminer DB GUI (System: PostgreSQL, Server: db)

# --- Migrations (run inside the api container) ---
docker compose exec api alembic upgrade head                       # apply (also auto on boot)
docker compose exec api alembic revision --autogenerate -m "msg"   # generate, then READ it
docker compose exec api alembic current                            # show current revision

# --- Tests (image lacks dev tools, so install them into the container first) ---
docker compose exec api pip install -r requirements-dev.txt        # one-time per running container
docker compose exec api pytest                                     # run the suite
docker compose exec api pytest tests/test_api.py::test_watchlist_crud   # a single test

# --- Optional: .venv for EDITOR SUPPORT ONLY (not how you run the app) ---
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# --- Optional / advanced: run on the host without Docker (see section 12) ---
docker compose up -d db          # start just Postgres on localhost
alembic upgrade head             # migrate against localhost (URL must use localhost, not db)
uvicorn main:app --app-dir src --reload   # NOT the recommended path
```

---

*Happy learning. The best way to internalize this is to run `docker compose up
--build`, open `/docs`, create a watchlist item, and watch the row appear in
Adminer — then read the four files that made that happen:
`main.py` → `watchlist.py` → `schemas.py` → `models.py`.*
