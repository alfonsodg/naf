# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
  category), `PATCH /feeds/{id}` (rename, move category, pause), and
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
- Intake limits that keep a large import inside the request budget: a
  per-host probe limit beside the global one, a bounded retry with backoff for
  a host that answers `429`, and a batch limit in size and in time. The
  candidates that do not fit are reported as `not_processed` instead of being
  dropped.
- Readiness probe (`GET /api/v1/health/ready`) that verifies PostgreSQL and the
  Miniflux API and reports each dependency separately.
- Structured JSON logging with correlation identifiers (`feed_id`,
  `ingestion_run_id`, `digest_id`) and no secret values.
- Typed configuration with fail-fast required values and the `NAF_`
  environment prefix.
- Miniflux reader adapter (REST API only) with normalized error handling.
- Ingestion collector with per-feed failure isolation and preserved
  provenance.
- README/entry endpoints for health, feeds, feed health, entries, read status,
  OPML import/export, and one ingestion pass.
- NAF-owned schema: digests, digest stories, entities, ingestion runs, and
  audio assets, with an initial Alembic migration.
- Repository standards: `docs/STANDARDS.md`, `docs/DEPLOYMENT.md`,
  `CHANGELOG.md`, canonical label families, and multi-stage container image.

### Changed

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
