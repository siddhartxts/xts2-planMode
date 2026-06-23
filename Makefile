# -----------------------------------------------------------------------------
# Developer command menu for this FastAPI + Postgres project.
#
# Docker is the normal way to run everything. Type "make" (or "make help") to
# see the list below. Most commands are short wrappers around "docker compose"
# so you don't have to remember the long forms.
#
# Typical flow:  make up  ->  make logs  ->  make down
# Tip: start the stack with "make up" first; the other Docker commands
#      (logs, ps, shell, migrate, ...) act on those running containers.
# -----------------------------------------------------------------------------

# Running plain "make" shows the help menu instead of doing nothing.
.DEFAULT_GOAL := help

# These are command names, not real files, so we mark them "phony".
.PHONY: help up down restart logs ps shell db-shell migrate revision \
        install dev test fmt clean

help:           ## show this list of commands
	@echo "Run the project (Docker):"
	@echo "  make up         build and start everything in the background"
	@echo "  make down       stop and remove the containers"
	@echo "  make restart    restart the running containers"
	@echo "  make logs       follow the API logs (Ctrl+C to stop watching)"
	@echo "  make ps         show which containers are running"
	@echo "  make shell      open a shell inside the API container"
	@echo "  make db-shell   open a psql prompt inside the database"
	@echo ""
	@echo "Database migrations (run inside the API container):"
	@echo "  make migrate            apply all migrations"
	@echo "  make revision m=\"msg\"   create a migration from model changes"
	@echo ""
	@echo "Local dev (run on your machine, not Docker):"
	@echo "  make install    install Python dependencies (incl. test tools)"
	@echo "  make dev        run the API locally with autoreload"
	@echo "  make test       run the test suite"
	@echo "  make fmt        format the code with black"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean      stop everything AND delete the database volume"

# --- Run the project with Docker ---------------------------------------------

up:             ## build and start the full stack in the background
	docker compose up -d --build

down:           ## stop and remove the containers (keeps the database data)
	docker compose down

restart:        ## restart the running containers
	docker compose restart

logs:           ## follow the API container logs
	docker compose logs -f api

ps:             ## show the status of the containers
	docker compose ps

shell:          ## open a shell inside the running API container
	docker compose exec api sh

db-shell:       ## open a psql prompt inside the database container
	# Uses the DB user/name from the db container's own environment.
	docker compose exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

# --- Database migrations (Alembic, run inside the API container) --------------

migrate:        ## apply all Alembic migrations
	docker compose exec api alembic upgrade head

revision:       ## create a migration:  make revision m="add foo"
	docker compose exec api alembic revision --autogenerate -m "$(m)"

# --- Local dev tools (run on the host, NOT in Docker) ------------------------

install:        ## install runtime + dev dependencies on your machine
	pip install -r requirements-dev.txt

dev:            ## run the API locally with autoreload (needs a reachable DB)
	uvicorn main:app --app-dir src --reload

test:           ## run the test suite (uses an in-memory SQLite DB)
	pytest

fmt:            ## format code with black
	black src alembic tests

# --- Cleanup -----------------------------------------------------------------

clean:          ## stop the stack and DELETE the database volume (data loss!)
	docker compose down -v
