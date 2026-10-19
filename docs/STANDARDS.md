# Standards

| | |
|---|---|
| **Project** | naf — Categorized feed aggregator with audio reports |
| **Version** | Unreleased |
| **Created** | 2026-10-18 |
| **Updated** | 2026-10-18 18:20 |
| **Author** | Alfonso de la Guarda Reyes |
| **Location** | `docs/STANDARDS.md` |

Development standards applied in this repository. Each rule below is
enforced by configuration or by a test, not by convention alone.

## Language and runtime

- Python `>=3.12`, run with the version pinned in the image (`python:3.13-slim`).
- `uv` is the only package manager. Never `pip install` into the environment.
- Code, comments, docstrings, commit messages, branches, and issue text are
  English. Product output (reports and audio) is Spanish.

## Package manager and dependencies

- Dependencies are declared in `pyproject.toml`; `uv.lock` is committed.
- Runtime, development, and optional (`audio`) groups are separated.
- `uv sync --extra dev` reproduces the development environment.
- `uv audit` runs in CI over the default and `dev` groups. Known advisories are
  triaged in an issue; advisories reachable only through the optional `audio`
  extra do not block the runtime image, which never installs it.
- `pytest` is pinned below 9.0 because `podcastfy` (the `audio` extra) requires
  `pytest>=8.3.3,<9.0.0`. This is a hard upstream constraint, not a choice.

## Licence policy

The project is Apache-2.0. That licence covers this repository, not its
dependencies, model weights, voices, or prompt templates.

- **Licence inventory.** Every dependency is inventoried with its declared
  licence before a distribution artefact is built. The current inventory is
  recorded in issue #2; it is generated from installed package metadata, not from
  documentation.
- **`psycopg` is LGPL-3.0-only** and is the only copyleft package in the runtime
  set. LGPL permits use from Apache-2.0 code while the library stays unmodified
  and replaceable. Two consequences are binding:
  - never vendor, patch, or fork `psycopg` inside this repository;
  - never build a single-file artefact that statically bundles it without
    revisiting this policy.
- **MPL-2.0** (`certifi`, `pathspec`) is file-level copyleft. Unmodified use
  carries no obligation beyond keeping notices. `pathspec` is development-only.
- **Dev-only licences do not gate distribution.** `pytest`, `ruff`, `mypy`,
  `bandit`, and `coverage` never enter the runtime image.
- **Never invent a licence.** Where package metadata declares none (`bandit`,
  `coverage`, `python-dotenv`), record it as undeclared rather than assuming the
  project's usual licence.
- **No scanning tool decides this.** Model weights, TTS voices, and feed content
  are out of scope for any dependency scanner and are reviewed when Phase 5
  selects an audio engine.

## File structure

```text
src/app/
  adapters/        Infrastructure implementations of the ports
    http/          Outbound HTTP probes (feed validation)
    miniflux/      Reader REST API client
    storage/       Audio persistence
  core/            Settings, exceptions, and ports
    ports/         Interfaces used for dependency inversion
  db/              SQLAlchemy base, session, migrations
  models/          ORM entities owned by NAF
  routers/         Thin HTTP handlers
  schemas/         Pydantic request/response and domain schemas
  services/        Business logic
tests/
  unit/            Isolated logic and contract tests (run locally)
  integration/     Persistent-service tests (remote test server only)
deploy/
  compose/         Development orchestration
  dev|qa|rev|prod/ Environment manifests
samples/           Safe configuration templates
```

Layering is one-directional: `routers → services → core.ports`, with adapters
implementing `core.ports`. Ports and schemas never import adapters, routers,
services, or `db`; `tests/unit/test_app_structure.py` enforces this.

## Code patterns

- Dependency inversion: services receive a port, never a concrete adapter.
- Fail-fast configuration: required values (database DSN, Miniflux URL and
  token) have no defaults; startup fails instead of falling back silently.
- Errors are domain exceptions from `src/app/core/exceptions.py`; routers
  translate them into the documented error envelope.
- No silent data loss: entries without a publication date are kept, and
  per-feed failures never abort an ingestion pass. The normalized entry keeps
  the attachments and the tags the feed provided, because an audio enclosure
  is part of the provenance of a podcast entry.
- Public functions and classes carry docstrings stating responsibility and
  inputs/outputs. Commented-out code is not committed.
- Timestamps cross the API as ISO-8601 and are normalised to UTC at the
  boundary; a value without a zone is read as UTC. The reader receives unix
  timestamps, which is the format its API expects.

## Linting and formatting

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src/
uv run bandit -r src/ -q
```

- ruff: line length 120, rule set `E, W, F, I, N, UP, B, S, C4, SIM, RUF`,
  `E501` ignored because the formatter owns width.
- mypy: `strict = true` over `src/`; Alembic imports are the only override.
- bandit: no findings permitted under `src/`.

## Testing

```bash
uv run pytest tests/unit -q                 # local, no external services
uv run pytest tests/ --cov=src --cov-report=term-missing
```

- Unit and contract tests run locally on every change.
- Integration tests require a persistent database or a live Miniflux instance
  and therefore run only on the designated remote test server recorded in
  `REMOTE.md`. No database, cache, or container runtime is installed locally.
- New code targets 80% line coverage; changed lines target 95%.
- Significant changes follow TDD: the failing test exists before the
  implementation. Trivial fixes use basic validation instead.
- Deterministic literals are allowed in test fixtures only, and never contain
  real credentials.

## Naming conventions

- Modules and functions: `snake_case`. Classes: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Ports describe capability (`FeedReader`), adapters name the technology
  (`MinifluxClient`).
- JSON fields are `snake_case`; routes are plural nouns in kebab-case when
  multi-word.

## Configuration

- Typed settings in `src/app/core/config.py`, prefix `NAF_`.
- Every variable is documented in `env.dev`, `env.qa`, `env.rev`, and
  `env.prod`; `samples/.env.example` is the copyable template.
- Adding, renaming, or removing a variable updates the matching `env.*` files
  in the same change.

## Data ownership

Reader state (feeds, entries, read flags, categories) belongs to Miniflux and
is accessed only through its REST API. Accessing Miniflux tables directly is
prohibited. NAF owns digests, citations, audio assets, classification, and
ingestion runs in its own PostgreSQL database.

## Feed intake and validation

A feed URL arriving from a pasted list, an OPML export, or a form field is
untrusted input. Two rules follow, and both are binding.

**Validation precedes insertion.** Every candidate is probed over HTTP before
the reader is asked to store it. A catalogue's own "active" flag is not
evidence: measured catalogues carry 4–25 % dead feeds. The probe produces
exactly one verdict:

| Verdict | Meaning | Action |
| --- | --- | --- |
| `alive` | HTTP 2xx and at least one `<item>` or `<entry>` | added enabled |
| `empty` | HTTP 2xx but no entries | reported, not added |
| `http_error` | 404, 410, dead domain, or a non-feed document | reported, not added |
| `throttled` | 401, 403, 405, 406, 409, 418, 429 | added **disabled**, reported unverified |
| `timeout` | no response within the configured limit | reported, not added |
| `blocked` | forbidden scheme, host, or redirect target | reported, not added |

`not_processed` is not a probe verdict but a report outcome: the batch limit
or the time budget left that candidate out. It is reported so the caller knows
the payload was only partly handled, and sending the same payload again
continues where the call stopped, because the candidates already added come
back as duplicates.

`throttled` is deliberately distinct: a host that refuses automated clients
(Reddit, several CDNs) still serves the same feed to a browser. Treating that
as a dead feed would discard a valid subscription, so it is added paused rather
than dropped. The reader downloads the feed before storing it, even when the
creation asks for a disabled feed, so the creation is attempted first and, when
the reader refuses it too, the feed is stored through the reader's OPML import,
which downloads nothing and marks the feed as disabled.

**Feeds are created one at a time.** `POST /v1/feeds` fetches and parses a feed
before inserting it; `POST /v1/import` inserts straight into the database
without fetching anything and is not atomic. Bulk intake therefore uses the
per-feed endpoint and keeps its own report, and `POST /opml/import` is
deprecated. The import is used for one case only, a feed whose host refuses
automated clients, where storing the subscription without downloading it is the
whole point.

**One feed, one applied category.** The reader holds a single category per
feed, so a feed found under several folders is applied to the first one and
the rest are only reported. The report names the applied category and the
reported folders separately, so it never claims an organisation the reader does
not have. The reported folders are NAF-owned data, kept in `feed_folders` and
readable through `GET /api/v1/feeds/folders`, because they are the only trace
of the tags the user had.

**Intake stays inside the request budget.** A global limit bounds the probes
of one batch and a second limit bounds the probes against a single host, so a
catalogue that points many URLs at one server never floods it. A host that
answers `429` is retried after the delay it asks for, and the number of
retries is bounded. The batch is bounded in size and in time as well, so a
large import cannot outlast the reverse proxy and leave the caller without a
report.

**SSRF is refused before the network.** Only `http` and `https` are accepted;
credentials in the authority, loopback, private, link-local, reserved, and
metadata targets are rejected, and every redirect hop is re-validated because
httpx would otherwise follow one into a private address. The hostname is also
resolved before the connection, and every resolved address must be globally
routable. The request then pins the validated address while keeping the
original name in the `Host` header and in the TLS server name, so a second
lookup cannot move the socket to another target. This holds even with a
single user and no public exposure.

## Git conventions

- Branches: `feature/*`, `fix/*`, `docs/*`, `refactor/*`, `test/*`, created
  from `develop`.
- Commits: `<type>(<scope>): <subject> (#N)` plus a `Ref #N` footer. Never
  `Closes #N`; issues close manually after review.
- One label per family on every issue: `status::`, `priority::`, `type::`,
  `source::`, `area::`.
- Never bypass hooks with `--no-verify` and never force-push.

## Glossary

| Term | Definition |
|---|---|
| Port | Interface a service depends on; implemented by an adapter |
| Adapter | Infrastructure implementation of a port (Miniflux, storage, TTS) |
| Provenance | Source identifiers kept with every entry: feed, URL, author, date |
| Digest | Generated report with claims, citations, period, and version |
| Fail-fast | Startup error on missing configuration instead of a silent default |
