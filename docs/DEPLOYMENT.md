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
  `X-Auth-Token` header. Communication is API-only. In development the URL
  points at the `miniflux` service of the compose stack.
- Neither database is exposed outside the internal network.

## Exposure boundary

The MVP has no authentication layer, because it is built for a single private
user. The service must therefore never be exposed to a public interface: it
creates subscriptions, triggers outbound downloads, and will generate the
reports.

- The API is reachable from the local host or from an internal network only.
- Any exposure to a public interface requires an authentication layer first,
  and that layer is a separate decision, not a configuration tweak.
- The development stack publishes the API port on the loopback interface for
  that reason. The reader keeps its own administrator credentials and is not
  the complement's concern.
- The rule applies to every environment, including a test one. A test server
  reachable from the internet is exposed too.

## Persistent storage

| Volume | Mount | Content | Inviolable |
| --- | --- | --- | --- |
| `naf-db` | `/var/lib/postgresql/data` | NAF PostgreSQL data | Yes |
| `naf-audio` | `/data/audio` | Generated audio assets | Yes |
| `miniflux-db` | `/var/lib/postgresql/data` | Reader PostgreSQL data | Yes, owned by the reader |
| `miniflux-data` | `/var/lib/miniflux` | Reader state | Yes, owned by the reader |

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
curl -fsS "$NAF_BASE_URL/api/v1/health/ready"
curl -fsS "$NAF_MINIFLUX_URL/healthcheck"
```

- `/health` is a liveness probe: it answers 200 as long as the process is up and
  never touches a dependency.
- `/api/v1/health/ready` is the readiness probe: it verifies PostgreSQL and the
  Miniflux API, returns 200 when both respond, and 503 with a per-dependency
  breakdown when either fails. A load balancer should route on this endpoint.
- Miniflux's `/healthcheck` returns 200 with body `OK`.

A liveness 200 is a smoke check only and does not replace endpoint-level tests.

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
