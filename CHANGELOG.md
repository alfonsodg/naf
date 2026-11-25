# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Entry classification and model tracking: `POST /api/v1/entries/{id}/classify`
  stores a topic, tags, publication type, officiality, confidence, and the
  models the entry names with a literal evidence quote; `PATCH` records the
  user's correction and a later automatic pass never overwrites it, and
  `GET /classifications?review_needed=true` lists what the model could not
  place.
- Auth proxy in the compose stack: a tracked nginx service
  (`deploy/proxy/nginx.conf`, `nginx:1.27-alpine`) terminates HTTP Basic auth
  and forwards to `http://naf:8000`, while the API keeps its loopback
  publication. `/health` stays unauthenticated for the healthcheck; the
  password file is a deployment artefact and is never committed.
- Reader retention: the stack declares decision 8's window instead of the
  reader's inherited defaults — 90 days after an entry is read, 180 for unread
  entries, cleanup once a day — and the deployment reference states what the
  reader deletes, what NAF keeps of a citation, and what happens when the cited
  entry has been archived.
- Pilot metrics: `GET /api/v1/metrics?days=7` reads the observation window from
  NAF-owned ingestion runs, report editions, and audio assets plus the reader's
  feed list. Freshness and stale sources, pass success, report and audio rates,
  p50/p95 wall time, and totals are returned in one snapshot; a reader failure
  degrades only the source block. `docs/PILOT_PLAN.md` fixes the 12-feed cohort,
  the seven-day window, the security and accessibility checks, and the
  go/no-go rules.

- Web interface: the same FastAPI service renders a Spanish screen to create a
  report, read its stories with every citation linked to the original URL,
  play the stored audio, and follow the synchronized transcript by segment.
  `GET /sources` lists the reader feeds with their category and last check, and
  `POST /ui/reports/{report_id}/audio` synthesizes an edition and returns to it
  with a recoverable notice. The pages reuse the API services and never expose
  Miniflux to the browser.
- Report audio: `POST /api/v1/reports/{report_id}/audio` synthesizes the stored
  edition with Kokoro ONNX and a Spanish voice, segments the script by sentence,
  concatenates one mono 24 kHz WAV, and keeps it as an immutable asset that
  `GET /reports/{id}/audio` serves. The report detail lists the asset, a second
  request reuses it, and a synthesis failure leaves the text untouched.
- On-demand text reports: `POST /api/v1/reports` selects entries by period,
  feeds, categories, tags, search, read/starred state, or the saved cursor,
  writes a Spanish report with a citation for every claim, and stores the
  edition with its filters, entries, model, and version. An empty selection
  returns `status: no_news` with an explicit message, and the history is
  readable through `GET /api/v1/reports` and `/reports/{id}`.
- Container publishing: a tag push builds the multi-stage image and pushes
  `ghcr.io/alfonsodg/naf:<tag>` plus a `sha-<short>` tag to GHCR, with layer
  caching and no build on a plain branch push.
- Entry tag filter: `GET /api/v1/entries` accepts a repeated `tags` parameter,
  forwarded to the reader in that form and combined with AND, so an entry must
  carry every requested tag and each added tag narrows the list.
- Ingestion run history: `GET /api/v1/ingestion-runs` lists the recorded passes
  newest first with pagination and an optional `status` filter, and
  `GET /api/v1/ingestion-runs/{run_id}` serves one pass with its per-feed
  errors, or the documented `INGESTION_RUN_NOT_FOUND` 404 envelope.
- The entry projection keeps the reader's last known modification beside the
  other two dates: `published_at` is what the publisher declares, `created_at`
  is when the reader captured the entry, and `changed_at` is the modification.
- `POST /api/v1/collect` accepts an optional `since` timestamp, read as UTC
  when it carries no zone, that scopes the pass to entries published at or
  after the cutoff; an undated entry is kept instead of being dropped.
- Curated technical radar feed pack (`feeds/alfonso-articles.opml`) with 18
  validated feeds and the approved taxonomy in the outline trail, plus
  `feeds/README.md` with the mapping, the validation record, and the import
  command.
- Feed intake (`POST /api/v1/feeds/intake`) that accepts a pasted list of URLs
  (one per line) or an OPML export and validates every candidate over HTTP
  before adding it, with a per-URL report of verdict, status, item count, and
  outcome.
- Feed validation with six distinct verdicts: `alive`, `empty`, `http_error`,
  `throttled`, `timeout`, and `blocked`. Only `alive` feeds are added enabled;
  `throttled` feeds are added disabled as unverified instead of being discarded.
- A `throttled` feed whose host also refuses the reader is now kept through the
  reader's OPML import, which stores the subscription without downloading it,
  so the documented promise of never discarding it holds. A refused creation
  reports the verdict and the HTTP status in the error envelope.
- Single-feed management: `POST /feeds` (validated add with an optional
  category), `PATCH /feeds/{id}` (rename, move category, pause),
  `DELETE /feeds/{id}` (remove the subscription), and
  `POST /feeds/{id}/refresh`; `GET /categories` lists reader categories.
- Entries can be filtered by publication period: `GET /api/v1/entries` accepts
  `published_after` and `published_before` as ISO-8601 timestamps, read as UTC
  when they carry no zone, and sends them to the reader as unix timestamps.
- `GET /api/v1/entries/{id}` serves one entry with the same shape the list
  returns, and every entry keeps the attachments and the tags the feed
  provided.
- SSRF protection for every candidate URL: `http`/`https` only, no credentials
  in the authority, and loopback, private, link-local, reserved, and metadata
  targets refused, including on each redirect hop.
- Host resolution for every candidate feed: the name is resolved before the
  connection and every resolved address must be globally routable, and the
  request pins the validated address while keeping the original name in the
  `Host` header and the TLS server name.
- OPML parsing that preserves folder nesting as categories and reports a feed
  appearing under several tags instead of keeping only the first, which is what
  Miniflux's own importer does.
- The intake report now names the category that was applied and the folders
  that were only reported, separately. The reported folders are kept in the NAF
  database and readable through `GET /api/v1/feeds/folders`, because the reader
  holds one category per feed.
- Settings `NAF_FEED_VALIDATION_TIMEOUT`, `NAF_FEED_VALIDATION_CONCURRENCY`,
  `NAF_FEED_VALIDATION_MAX_REDIRECTS`, and `NAF_FEED_INTAKE_MAX_BYTES` in every
  environment file.
- A candidate response is streamed and capped while it is read, so a server
  that sends an endless document is refused instead of being buffered in full.
- Intake limits that keep a large import inside the request budget: a
  per-host probe limit beside the global one, a bounded retry with backoff for
  a host that answers `429`, and a batch limit in size and in time. The
  candidates that do not fit are reported as `not_processed` instead of being
  dropped. The time bound is a wall-clock bound: the chunk is sized from the
  per-host limit and the retry count, so a same-host batch cannot outlast it.
- Readiness probe (`GET /api/v1/health/ready`) that verifies PostgreSQL and the
  Miniflux API and reports each dependency separately.
- The development compose stack brings up the reader too: `miniflux` and
  `miniflux-db`, with their own named volumes, so the environment that
  exercises the whole product comes up on its own.
- The deployment contract states the public-exposure boundary of the
  unauthenticated API, and the development stack publishes its port on the
  loopback interface only.
- Structured JSON logging with correlation identifiers (`feed_id`,
  `ingestion_run_id`, `digest_id`) and no secret values.
- Typed configuration with fail-fast required values and the `NAF_`
  environment prefix.
- Miniflux reader adapter (REST API only) with normalized error handling.
- The feed list is projected onto a NAF-owned shape, the same one the feed
  health report uses, so the reader's own fields, its scraping rules, the
  credentials of an authenticated feed, and its icon never reach the API.
- Ingestion collector with per-feed failure isolation and preserved
  provenance.
- Every ingestion pass is recorded in the NAF database as an ingestion run:
  when it started and finished, whether it succeeded or a feed failed, the
  entry count, and the per-feed errors. The run identifier is returned by
  `POST /collect` and carried in the structured logs.
- README/entry endpoints for health, feeds, feed health, entries, read status,
  OPML import/export, and one ingestion pass.
- NAF-owned schema: digests, digest stories, entities, ingestion runs, and
  audio assets, with an initial Alembic migration.
- Repository standards: `docs/STANDARDS.md`, `docs/DEPLOYMENT.md`,
  `CHANGELOG.md`, canonical label families, and multi-stage container image.

### Fixed

- Feed addresses are pinned to IPv4 when the host resolves to both families.
  Sorting addresses as text put `2001:…` before `64.…`, and a container without
  an IPv6 route reported reachable feeds as `http_error` (#44).
- The compose stack forwards `NAF_FEED_INTAKE_MAX_BYTES` to the container, so a
  validated feed larger than 1 MB can be imported when the deployment raises
  the cap (#45).
- The runtime image copies the `README.md` that `pyproject.toml` names, ships
  `alembic.ini`, and builds its virtual environment at `/app/.venv` so the
  console scripts and the non-editable install work after the copy (#43).

### Changed

- The reader's browser-facing address is a deployment value
  (`NAF_MINIFLUX_BASE_URL`), so a published host does not need an SSH tunnel and a
  local stack keeps `http://localhost:8080` by default.
- The entry routes moved to `src/app/routers/entries.py`; every URL path and
  response shape is unchanged.
- The reader polls every 20 minutes with the `round_robin` scheduler and 50
  feeds per pass, inside decision 4's 15-30 minute window. The three values are
  declared through `NAF_MINIFLUX_POLLING_FREQUENCY`,
  `NAF_MINIFLUX_POLLING_SCHEDULER`, and `NAF_MINIFLUX_BATCH_SIZE` in every
  environment file and in the development stack, so the cadence is stated
  instead of inherited from the reader's defaults.
- `DELETE /api/v1/feeds/{id}` now states what the reader does: the subscription
  and every entry it carried are deleted, the response keeps `feed_id` and
  `removed` and adds a `warning` that names the cascade, and
  `docs/STANDARDS.md` no longer claims the entries stay untouched. Pausing with
  `PATCH /feeds/{id}` is the non-destructive way to stop following a feed.
- `opentelemetry-api` pinned to 1.45.2 in `uv.lock`, the first release past
  advisory GHSA-mf5v-w3w3-f6cg, which was failing the dependency audit.
- `POST /api/v1/opml/import` is deprecated in favour of `POST /feeds/intake`:
  Miniflux stores an imported OPML without fetching anything, so dead feeds
  enter the reader silently and the import is not atomic.
- `defusedxml` added as a runtime dependency (PSF-2.0) for OPML parsing, with
  `types-defusedxml` as a development-only stub package.
- The ten plan decisions are approved and recorded in `docs/PRODUCT_PLAN.md`
  section 17 and issue #2; they are binding for the MVP.
- `docs/STANDARDS.md` now documents the licence policy, including the `psycopg`
  LGPL-3.0 constraint on packaging.
- Documentation is English-only across the repository; the product
  specification moved to `docs/PRODUCT_PLAN.md`.
- Dependency audit (`uv audit`) added to CI, scoped to the deployed dependency
  set (the optional `audio` extra is excluded).
- Source moved to the mandatory `src/app/` layout with ports in
  `src/app/core/ports/` and schemas in `src/app/schemas/`.
- Tooling aligned with project standards: ruff line length 120 with the
  documented rule set, mypy strict, bandit, and coverage-aware pytest.

### Removed

- Non-canonical auxiliary documentation and unused service stubs.

## [0.1.0] - 2026-10-18

Initial skeleton: contracts, ORM models, migration, and API scaffolding.
