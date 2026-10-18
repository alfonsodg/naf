# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
