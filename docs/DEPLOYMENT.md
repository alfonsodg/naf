# Deployment

| | |
|---|---|
| **Project** | naf — Categorized feed aggregator with audio reports |
| **Version** | Unreleased |
| **Created** | 2026-10-18 |
| **Updated** | 2026-11-24 |
| **Author** | Alfonso de la Guarda Reyes |
| **Location** | `docs/DEPLOYMENT.md` |

Operational deployment reference for `naf`. Read together with `REMOTE.md`,
the local-only ground truth for hosts, ports, and credentials.

## Topology

Three runtimes plus one external dependency:

| Component | Role | Ownership |
| --- | --- | --- |
| `proxy` | Public edge: HTTP Basic auth in front of the API | This repository, `deploy/proxy/nginx.conf` |
| `naf` | Complement API: reports, citations, audio, classification | This repository |
| `db` | NAF persistence: digests, citations, entities, audio metadata | This repository |
| `miniflux` | Feed reader: subscriptions, entries, read state, categories | External (Apache-2.0) |
| `miniflux-db` | Miniflux persistence | Miniflux; never accessed by NAF |

```text
          ┌───────────┐       ┌──────────┐       ┌───────────┐       ┌─────────┐
 client ──▶│   proxy   │──────▶│   naf    │──────▶│ miniflux  │──────▶│  feeds  │
          │  :18082   │ HTTP  │  :8000   │ REST  │   :8080   │ HTTP  │ (public)│
          │ basic auth│       │ loopback │       │           │       │         │
          └───────────┘       └────┬─────┘       └───────────┘       └─────────┘
                                   │
                                   ▼
                              ┌──────────┐
                              │    db    │  naf-owned data only
                              │  :5432   │
                              └──────────┘
```

Service names (`proxy`, `naf`, `db`) are fixed once deployed. Other services and
any reverse proxy resolve them by DNS name; renaming breaks the deployment.

## Networking

- `proxy` publishes the only public port and forwards to `http://naf:8000`
  over the compose network. It is the only service meant to be reachable from
  outside the host.
- `naf` exposes `/health` for liveness and `/api/v1/*` for the API, published on
  `127.0.0.1` only.
- Miniflux is reached over HTTP using `NAF_MINIFLUX_URL` with an
  `X-Auth-Token` header. Communication is API-only. In development the URL
  points at the `miniflux` service of the compose stack.
- Neither database is exposed outside the internal network.

## Reader base URL

`NAF_MINIFLUX_BASE_URL` is the address a browser uses to reach the reader. Miniflux
builds its links and session cookies from it, so it must match the published host and
port, not the internal service name. The internal API stays on `http://miniflux:8080`
through `NAF_MINIFLUX_URL`.

| Deployment | `NAF_MINIFLUX_BASE_URL` |
| --- | --- |
| Local compose | `http://localhost:8080` (default) |
| Sandbox, published port 18081 | `http://<host-address>:18081` |

The NAF API keeps its own loopback publication: publishing the reader does not publish
the API, which has no authentication layer of its own. The edge proxy below is the
only public surface.

## Public API surface (auth proxy)

The API has no authentication of its own, so its only public surface is the
`proxy` service: an nginx container that terminates HTTP Basic authentication
and forwards to `http://naf:8000` over the compose network. The API keeps its
loopback publication (`127.0.0.1:<NAF_PORT>:8000`); publishing port 8000 on
any other interface bypasses the proxy and is forbidden.

| Variable | Default | Purpose |
| --- | --- | --- |
| `NAF_PROXY_PORT` | `18082` | Host port that publishes the proxy container port 8080 |
| `NAF_PROXY_HTPASSWD` | `../proxy/htpasswd` | Host path of the password file, mounted read-only at `/etc/nginx/htpasswd` |

The config is tracked at `deploy/proxy/nginx.conf`: `server_tokens off`, a 300 s
read timeout for report generation and audio synthesis, an 8 MB body limit, and
a request limit on `POST /api/v1/reports` (1 request/s, burst 10). `/health` is
the only unauthenticated path, so the container healthcheck and an external
liveness probe work; every other path answers `401` without credentials.

The password file is a deployment artefact and lives outside the repository: in
a deployment, point `NAF_PROXY_HTPASSWD` at an absolute path outside the
checkout, such as `/srv/naf/proxy/htpasswd`. Create it with
`htpasswd -c -B <path> <user>` under `umask 077`, which leaves it at mode
`0600` while the password is written, then set `0644` so the nginx worker can
read it through the read-only mount. It is never committed, never copied into
an image, and never written into the compose file; the repository default
`deploy/proxy/htpasswd` is gitignored only as a local convenience.

Plain HTTP sends the credentials in clear, so this is a test-host exposure
until TLS or a private network replaces it.

## Reader polling cadence

Polling follows decision 4: a feed is polled every 15 to 30 minutes. The
development stack declares the interval, the scheduler, and the batch instead
of relying on the reader's own defaults:

| Variable | Value | Meaning |
| --- | --- | --- |
| `NAF_MINIFLUX_POLLING_FREQUENCY` | `20` | Minutes between polls of one feed |
| `NAF_MINIFLUX_POLLING_SCHEDULER` | `round_robin` | Scheduler that hands due feeds to the poller |
| `NAF_MINIFLUX_BATCH_SIZE` | `50` | Feeds refreshed per scheduler pass |

`round_robin` spreads the pack across cycles without starving a low-frequency
source, and 50 leaves headroom over the 8-30 feed pack, so a pass never
truncates it. The reader still honours `Cache-Control`, `ETag`, and
`Last-Modified`, so polling every 20 minutes costs no full download of a feed
that did not change. Every `env.*` file carries the same three values, and the
compose file declares the same numbers as its defaults.

Verification, once the stack is up:

- `GET /api/v1/feeds` exposes `checked_at` per feed. It must move forward
  within one interval plus the reader's own run time; a feed that stays at the
  same instant is not being polled.
- The reader's own `GET /v1/feeds`, called with the API token, also carries
  `next_check_at`, the instant the scheduler planned for that feed. The NAF
  projection does not expose it, so read it from the reader when the schedule
  itself is in question.
- `GET /api/v1/feeds/health` reports the freshness and the parsing errors of
  every feed, which is where a poll that keeps failing becomes visible.

## Retention

Decision 8 fixes an explicit retention window, and the stack declares it instead
of inheriting the reader's defaults (60 days for read entries and 180 for
unread):

| Variable | Value | Meaning |
| --- | --- | --- |
| `NAF_MINIFLUX_CLEANUP_READ_DAYS` | `90` | Days after an entry is read before the reader archives it |
| `NAF_MINIFLUX_CLEANUP_UNREAD_DAYS` | `180` | Days an unread entry stays before the reader archives it |
| `NAF_MINIFLUX_CLEANUP_FREQUENCY` | `24` | Hours between cleanup runs |

The window is 90 days, the top of the 30–90 range decision 8 approves: a read
entry stays a full quarter before it is archived. Unread entries get 180 days so
nothing expires before it has had a chance to be read, and the value is never
set below the read one. The cleanup runs once a day, so the window is exact to a
day. Every `env.*` file carries the same three values, and the compose file
declares them as its defaults.

What the reader deletes: non-bookmarked and non-shared entries past their
window, together with the content it stored for them, and it records a tombstone
so a later feed refresh cannot import the same entry again. The reader remains
the owner of entry content; NAF never mirrors it.

What NAF keeps: every stored report keeps, per story, its claims and citations.
Each citation carries the entry id, URL, title, and author captured when the
report was written (plus the optional quote and relevance score), and it lives
in the NAF database, not in the reader.

A citation whose entry was archived keeps its stored id, URL, title, and author:
the report detail still renders it and its URL opens at the publisher. The
reader no longer resolves that entry, and NAF cannot re-read the body or
regenerate that edition's source text from the reader; the NAF-owned report, its
citations, and its audio are untouched. Changing a cleanup value affects future
cleanup runs only, and no volume is deleted, truncated, or recreated for
retention.

## Runtime settings forwarded by the stack

The compose file forwards a curated set to the `naf` container. A setting that is
not listed here stays at the application default even when the env file changes
it, because the container never receives the variable.

| Variable | Default | Purpose |
| --- | --- | --- |
| `NAF_FEED_INTAKE_MAX_BYTES` | `1000000` | Largest feed document accepted during intake; enforced while the body is read |
| `NAF_LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API root for report generation |
| `NAF_LLM_API_KEY` | empty | Provider key; empty disables the report routes with `503` |
| `NAF_LLM_MODEL` | empty | Model id; empty disables the report routes with `503` |
| `NAF_LLM_TIMEOUT` | `120` | Seconds allowed for one completion |
| `NAF_LLM_MAX_OUTPUT_TOKENS` | `6000` | Hard ceiling on the tokens one report may return |
| `NAF_REPORT_MAX_ENTRIES` | `40` | Largest selection sent to the model; bounds the per-report cost |
| `NAF_REPORT_DEFAULT_DAYS` | `7` | Window used when a request names neither a period nor `since_last` |
| `NAF_TTS_MODEL_PATH` | `/models/kokoro-v1.0.onnx` | Kokoro ONNX model; empty disables the audio routes with `503` |
| `NAF_TTS_VOICES_PATH` | `/models/voices-v1.0.bin` | Voice bank; Spanish voices such as `ef_dora` live here |
| `NAF_TTS_VOICE` | `ef_dora` | Spanish voice used for synthesis |
| `NAF_TTS_SPEED` | `1.0` | Speech rate multiplier |
| `NAF_MODELS_DIR` | `/opt/naf/models` | Host directory mounted read-only at `/models` |

Raise the cap only for a validated source that publishes more than the default,
and keep the value bounded: it is a memory limit, not a preference.

`NAF_PROXY_PORT` and `NAF_PROXY_HTPASSWD` are consumed by the `proxy` service,
never forwarded to the `naf` container; `NAF_MINIFLUX_CLEANUP_*` is consumed by
`miniflux`, not forwarded to `naf` either.

## Edition cleanup

Report editions and their audio stay immutable inside the retention window
(decision 8, default 90 days). The service does not schedule the cleanup:
a caller previews it and then runs it explicitly.

```bash
# Preview: what would be removed, with no deletion
curl -u naf:<password> "http://127.0.0.1:18082/api/v1/maintenance/editions?days=90"

# Apply: deletes the files and the rows older than the window
curl -u naf:<password> -X POST \
  "http://127.0.0.1:18082/api/v1/maintenance/editions?days=90&dry_run=false"
```

`dry_run` defaults to `true`, so a mistaken call cannot delete. The cleanup
never touches reader data or ingestion runs, and a file that is already gone is
counted and skipped. A daily timer on the host is the expected operator:

```cron
30 4 * * * curl -sf -u naf:<password> -X POST "http://127.0.0.1:18082/api/v1/maintenance/editions?days=90&dry_run=false" >/dev/null
```

## Database migrations

The runtime image carries `alembic.ini` and the migration scripts under
`src/app/db/migrations`. The service does not create tables on startup: apply the
schema before the first start and after every image change that includes a
migration.

```bash
docker compose --env-file deploy.env -f deploy/compose/docker-compose.yml run --rm naf alembic upgrade head
```

The command reads `NAF_DATABASE_URL` from the environment the compose file already
provides, so no DSN is stored in the image or in `alembic.ini`.

## Exposure boundary

The API has no authentication layer of its own, because it is built for a
single private user: it creates subscriptions, triggers outbound downloads, and
generates reports. Its only guard is the edge proxy, so the API must never be
published directly.

- The API is published on the loopback interface only. Publishing port 8000 on
  any other interface bypasses the proxy and is forbidden.
- The proxy terminates HTTP Basic authentication on the only published port;
  every path except `/health` answers `401` without credentials.
- Any other exposure still requires an authentication layer and remains a
  separate decision, not a configuration tweak.
- The reader keeps its own administrator credentials and is not the
  complement's concern.
- The rule applies to every environment, including a test one. A test server
  reachable from the internet is exposed too, and Basic auth over plain HTTP
  sends the password in clear: TLS or a private network is required before this
  counts as more than a test exposure.

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
curl -fsS -u "<proxy-user>" "http://<host>:18082/health"
```

- `/health` is a liveness probe: it answers 200 as long as the process is up and
  never touches a dependency.
- `/api/v1/health/ready` is the readiness probe: it verifies PostgreSQL and the
  Miniflux API, returns 200 when both respond, and 503 with a per-dependency
  breakdown when either fails. A load balancer should route on this endpoint.
- Miniflux's `/healthcheck` returns 200 with body `OK`.
- The proxy answers `200` on `/health` with credentials and `401` without them;
  `<proxy-user>` is the user created in the password file.

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
| Edge proxy | nginx that authenticates and forwards to the API; the only public surface |
| Retention window | 90 days after an entry is read before the reader archives it |
| Tombstone | Reader record that stops an archived entry from being re-imported |
