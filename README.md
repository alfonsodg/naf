# naf

| | |
|---|---|
| **Project** | naf — Categorized feed aggregator with audio reports |
| **Version** | Unreleased |
| **Created** | 2026-10-18 |
| **Updated** | 2026-10-18 13:00 |
| **Author** | Alfonso de la Guarda Reyes |
| **Location** | `README.md` |

News aggregator with categorized feeds and on-demand audio reports in Spanish.

`naf` reuses [Miniflux](https://github.com/miniflux/v2) as the feed reader and
adds what it does not provide: on-demand Spanish text and audio digests with
mandatory citations, plus optional classification of model and product
announcements.

## Objectives

- Keep every entry from every subscribed feed readable and searchable.
- Preserve provenance: source feed, canonical URL, author, and publication
  date, including which content level the feed actually publishes.
- Generate Spanish reports and audio only on demand, with citations for every
  factual claim.
- Never duplicate the reader: subscriptions and read state stay in Miniflux.

## Status

Early implementation. Reader integration and the ingestion collector work.
Classification, reports, and audio are not implemented yet. Phases are tracked
as GitHub issues, with a meta-issue coordinating the rest.

## Features

- Reads all entries from every configured feed through the Miniflux REST API.
- Never filters during ingestion: selection belongs to the report step.
- Per-feed failure isolation: one broken feed never aborts a pass.
- Keeps entries without a publication date instead of dropping them.
- NAF-owned persistence for digests, citations, entities, and audio assets.

## Tech stack

Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, psycopg 3, httpx,
uv. PostgreSQL for persistence. Miniflux as the external reader.

## Quick start

```bash
uv sync --extra dev
cp samples/.env.example .env    # fill in the required values
uv run alembic upgrade head
uv run uvicorn app.main:app --app-dir src --reload --port 8000
```

Then open <http://localhost:8000/docs>. Required configuration has no
defaults: startup fails when a value is missing rather than falling back
silently.

## Quality checks

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src/
uv run bandit -r src/ -q
uv audit --no-extra audio --ignore GHSA-6w46-j5rx-g56g
uv run pytest tests/unit -q
```

## API

All versioned routes live under `/api/v1`. List responses carry pagination
metadata; errors use the documented envelope
`{"error": {"code", "message", "details"}}`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe for deployments |
| `GET` | `/api/v1/health` | Versioned liveness probe |
| `GET` | `/api/v1/health/ready` | Readiness: PostgreSQL and Miniflux |
| `GET` | `/api/v1/feeds` | List feeds with health metadata |
| `GET` | `/api/v1/feeds/health` | Freshness and parsing status per feed |
| `GET` | `/api/v1/feeds/folders` | Folders found for the feeds, besides the applied category |
| `POST` | `/api/v1/feeds` | Validate and add one feed, optionally into a category |
| `PATCH` | `/api/v1/feeds/{id}` | Rename, move to another category, or pause a feed |
| `POST` | `/api/v1/feeds/{id}/refresh` | Ask the reader to poll one feed now |
| `POST` | `/api/v1/feeds/intake` | Validate and add feeds from a URL list or an OPML export |
| `GET` | `/api/v1/categories` | List reader categories |
| `GET` | `/api/v1/entries` | List entries with filters and pagination |
| `PATCH` | `/api/v1/entries/{id}` | Set read or unread status |
| `GET` | `/api/v1/opml/export` | Export subscriptions as OPML |
| `POST` | `/api/v1/opml/import` | Deprecated: stores the OPML without validating its feeds |
| `POST` | `/api/v1/collect` | Run one ingestion pass |

`POST /api/v1/feeds/intake` takes either a text body with one feed URL per line
or an OPML document, validates every candidate over HTTP, and returns one report
row per input URL. Only a feed that answered with real entries is added enabled;
a host that blocks automated clients is reported and added paused, never
discarded. See `docs/STANDARDS.md` for the verdicts and the safety rules.

The intake keeps itself inside the request budget: probes run in parallel but
never more than a few against the same host, and a payload larger than the
configured batch limit is reported in full while only the candidates that fit
are probed. The rest come back as `not_processed`, so sending the same payload
again continues where the call stopped.

Each report row states the category that was applied and, separately, the
folders that were only found in the source document. The reader holds one
category per feed, so the extra folders are kept in the NAF database and can be
read from `GET /api/v1/feeds/folders`.

## Documentation

- `docs/STANDARDS.md` — stack, layout, tooling, testing, and conventions.
- `docs/DEPLOYMENT.md` — topology, volumes, migrations, health, and rollback.
- `docs/PRODUCT_PLAN.md` — product specification, scope, and phased delivery plan.
- `CHANGELOG.md` — change history.
- `REMOTE.md` — local-only operational inventory (never tracked).

## License

Apache-2.0. See `LICENSE`.
