# Deployment

| | |
|---|---|
| **Project** | naf — Categorized feed aggregator with audio reports |
| **Version** | Unreleased |
| **Created** | 2026-10-18 |
| **Updated** | 2026-10-18 13:00 |
| **Author** | Alfonso de la Guarda Reyes |
| **Location** | `docs/DEPLOYMENT.md` |

Operational deployment reference for `naf`. Read together with `REMOTE.md`,
the local-only ground truth for hosts, ports, and credentials.

## Topology

Two runtimes plus one external dependency:

| Component | Role | Ownership |
| --- | --- | --- |
| `naf` | Complement API: reports, citations, audio, classification | This repository |
| `db` | NAF persistence: digests, citations, entities, audio metadata | This repository |
| `miniflux` | Feed reader: subscriptions, entries, read state, categories | External (Apache-2.0) |
| `miniflux-db` | Miniflux persistence | Miniflux; never accessed by NAF |

```text
          ┌──────────┐        ┌───────────┐        ┌─────────┐
 client ──▶│   naf    │───────▶│ miniflux  │───────▶│  feeds  │
          │  :8000   │  REST  │   :8080   │  HTTP  │ (public)│
          └────┬─────┘        └───────────┘        └─────────┘
               │
               ▼
          ┌──────────┐
          │    db    │  naf-owned data only
          │  :5432   │
          └──────────┘
```

Service names (`naf`, `db`) are fixed once deployed. Other services and any
reverse proxy resolve them by DNS name; renaming breaks the deployment.

## Networking

- `naf` exposes `/health` for liveness and `/api/v1/*` for the API.
- Miniflux is reached over HTTP using `NAF_MINIFLUX_URL` with an
  `X-Auth-Token` header. Communication is API-only.
- Neither database is exposed outside the internal network.

## Persistent storage

| Volume | Mount | Content | Inviolable |
| --- | --- | --- | --- |
| `naf-db` | `/var/lib/postgresql/data` | NAF PostgreSQL data | Yes |
| `naf-audio` | `/data/audio` | Generated audio assets | Yes |
| Miniflux volume | Miniflux-defined | Reader state | Yes, owned by Miniflux |

Container-internal storage is prohibited: every durable path is a named volume
or an explicit host path. Existing volumes must never be unmounted, reformatted,
or recreated.

## Container image

- Multi-stage build (`Dockerfile`): builder installs the locked environment,
  runtime copies only `.venv` and `src/`.
- Runs as `nobody`; no secrets are baked into the image.
- Base image pinned to `python:3.13-slim`; `:latest` is never used.
- `HEALTHCHECK` calls `GET /health`.
- Builds and pushes happen only in CI/CD. Never build an image manually.

## Environment flow

| Environment | Platform | Manifest | Image tag |
| --- | --- | --- | --- |
| Development | Docker Compose | `deploy/compose/docker-compose.yml` | `dev-<identifier>` |
| QA | Recorded in `REMOTE.md` | `deploy/qa/` | `qa-<identifier>` |
| Review | Recorded in `REMOTE.md` | `deploy/rev/` | `rev-<identifier>` |
| Production | Recorded in `REMOTE.md` | `deploy/prod/` | approved release tag |

Every variable each environment needs is declared with its purpose in
`env.dev`, `env.qa`, `env.rev`, and `env.prod`. Values are supplied by CI/CD
or `REMOTE.md`; they are never committed.

## Zero-destruction update procedure

Absolute prohibitions during any test run or deployment:

- `docker compose down -v`
- `docker volume rm`, `docker volume prune`
- `dropdb`, `DROP DATABASE`, `DROP SCHEMA`
- blanket restarts that tear down the database or sibling services

Update a single service:

```bash
docker compose up -d --no-deps naf
```

## Migrations

- Alembic; revisions live in `src/app/db/migrations/versions`.
- The database URL comes from `NAF_DATABASE_URL` through application settings;
  it is never hardcoded in `alembic.ini`.
- Every migration defines both `upgrade()` and `downgrade()`.
- Apply forward only in deployed environments: `uv run alembic upgrade head`.
- Roll back one revision with `uv run alembic downgrade -1` only when the failed
  release included a migration.
- An applied revision is never edited; add a new one.

The initial migration is `435254b79450` (complement schema). Verify with
`uv run alembic heads`.

## Health verification

```bash
curl -fsS "$NAF_BASE_URL/health"
curl -fsS "$NAF_MINIFLUX_URL/healthcheck"
```

Expected: the first returns HTTP 200 with `{"status": "ok"}`; the second
returns HTTP 200 with body `OK`. A `/health` 200 is a smoke check only and does
not replace endpoint-level tests.

## Rollback

1. Re-deploy the previous immutable image tag.
2. Run `uv run alembic downgrade -1` only if the failed release added a
   migration.
3. Verify `/health`.
4. Record the incident and open an issue labeled `priority::critical`.

## Test boundaries

Unit and contract tests run locally. Any test that needs a real database, a
live Miniflux instance, or a container runtime runs on the designated remote
test server recorded in `REMOTE.md`. No database or cache is installed on the
local workstation.

## Glossary

| Term | Definition |
| --- | --- |
| Provenance | Source identifiers kept with every entry |
| Surgical update | Restarting one service with `--no-deps`, leaving data intact |
| Immutable tag | Image tag never reused once published |
| Smoke check | Liveness call that does not replace functional tests |
| Zero destruction | Prohibition on commands that can remove volumes or schemas |
