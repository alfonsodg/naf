# naf

| | |
|---|---|
| **Project** | naf — Categorized feed aggregator with audio reports |
| **Version** | Unreleased |
| **Created** | 2026-10-18 |
| **Updated** | 2026-11-24 |
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

Python 3.14, FastAPI 0.165, Pydantic 2.14, SQLAlchemy 2.1, Alembic 1.20,
psycopg 3.3, httpx, uv 0.13. PostgreSQL 18 for persistence. Miniflux 2.3.5 as
the external reader; Kokoro ONNX 0.6 for speech.

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

## Configuration

`src/app/core/config.py` holds the typed settings, read from the environment
with the `NAF_` prefix. `env.dev`, `env.qa`, `env.rev`, `env.prod`, and the
`samples/.env.example` template document every variable.

The reader's polling is declared with the rest: 20 minutes between polls
(`NAF_MINIFLUX_POLLING_FREQUENCY`), the `round_robin` scheduler
(`NAF_MINIFLUX_POLLING_SCHEDULER`), and 50 feeds per scheduler pass
(`NAF_MINIFLUX_BATCH_SIZE`). `docs/DEPLOYMENT.md` records that cadence and how
to verify it through `checked_at` and `next_check_at`.

Retention is declared too (decision 8): `NAF_MINIFLUX_CLEANUP_READ_DAYS=90`,
`NAF_MINIFLUX_CLEANUP_UNREAD_DAYS=180`, and
`NAF_MINIFLUX_CLEANUP_FREQUENCY=24` replace the reader's inherited cleanup.
A read entry stays a quarter before it is archived; an unread one gets six
months so it can still be read. NAF keeps, per cited story, the entry id, URL,
title, and author captured with the report and never a copy of the body, so a
citation remains identifiable after the reader archives its entry.
`docs/DEPLOYMENT.md` states the window, what the reader deletes, and what
happens to a citation whose entry was archived.

## Container image

The runtime image is published to GHCR by `.github/workflows/container.yml`.
A branch push never builds; a tag push does. Issue builds use
`<type>-<issue>-<n>` (for example `fix-45-1`) and releases use
`vMAJOR.MINOR.PATCH`:

```bash
git tag -a fix-45-1 -m "Container build for #45"
git push origin fix-45-1   # publishes ghcr.io/alfonsodg/naf:fix-45-1 and :sha-<short>
```

The image runs as `nobody`, exposes port 8000, and carries `alembic.ini`, so a
deployment applies the schema before starting:

```bash
docker compose --env-file deploy.env -f deploy/compose/docker-compose.yml run --rm naf alembic upgrade head
docker compose --env-file deploy.env -f deploy/compose/docker-compose.yml up -d
```

`deploy.env` supplies `NAF_IMAGE=ghcr.io/alfonsodg/naf:<tag>` and the required
variables. The stack forwards only the settings listed in
`docs/DEPLOYMENT.md`; anything else stays at the application default.

## Public surface

The API has no authentication of its own, so the stack publishes it only
through `proxy`, an nginx container that terminates HTTP Basic authentication
and forwards to `http://naf:8000` on the compose network. The `naf` service
keeps its loopback publication (`127.0.0.1:${NAF_PORT}:8000`); the proxy is the
only public surface. `deploy/proxy/nginx.conf` is tracked, the password file is
not, and a deployment keeps it outside the repository.

| Variable | Default | Purpose |
| --- | --- | --- |
| `NAF_PROXY_PORT` | `18082` | Host port that publishes the proxy |
| `NAF_PROXY_HTPASSWD` | `../proxy/htpasswd` | Host path of the password file, mounted read-only |

`/health` is the only unauthenticated path, because it is the liveness probe
and carries no data; every other path answers `401` without credentials. Plain
HTTP sends the password in clear, which is acceptable only on a test host until
TLS or a private network replaces it. `docs/DEPLOYMENT.md` records the
procedure and the file modes.

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
| `GET` | `/api/v1/folders` | Distinct stored folders with the number of feeds in each |
| `POST` | `/api/v1/feeds` | Validate and add one feed, optionally into a category |
| `PATCH` | `/api/v1/feeds/{id}` | Rename, move to another category, or pause a feed |
| `DELETE` | `/api/v1/feeds/{id}` | Remove one subscription and, with it, its entries |
| `POST` | `/api/v1/feeds/{id}/refresh` | Ask the reader to poll one feed now |
| `POST` | `/api/v1/feeds/intake` | Validate and add feeds from a URL list or an OPML export |
| `GET` | `/api/v1/categories` | List reader categories |
| `GET` | `/api/v1/entries` | List entries with filters, folders, tags, publication period, and pagination |
| `GET` | `/api/v1/entries/{id}` | Read one entry with its attachments and tags |
| `PATCH` | `/api/v1/entries/{id}` | Set read or unread status |
| `GET` | `/api/v1/opml/export` | Export subscriptions as OPML |
| `POST` | `/api/v1/opml/import` | Deprecated: stores the OPML without validating its feeds |
| `POST` | `/api/v1/collect` | Run one pass, optionally from a publication cutoff |
| `POST` | `/api/v1/reports` | Generate and store one cited report, selecting feeds, folders, or categories |
| `GET` | `/api/v1/reports` | List the stored reports, newest first |
| `GET` | `/api/v1/reports/{report_id}` | One report with its stories and citations |
| `GET` | `/api/v1/ingestion-runs` | List recorded passes with an optional status filter |
| `GET` | `/api/v1/ingestion-runs/{run_id}` | Read one recorded pass with its per-feed errors |
| `GET` | `/api/v1/metrics` | Pilot snapshot of sources, ingestion, reports, and audio |

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

The stored folders are also a filter, not only provenance. `GET /api/v1/folders`
lists them with their feed count, `GET /api/v1/entries` accepts a repeated
`folder` parameter beside the existing filters, and `POST /api/v1/reports`
accepts `folders` when no feed is named. The selector maps the stored feed URL
to the reader feed identifier with one `list_feeds()` call, so it never changes
the category the reader applied. A feed kept under two requested folders is read
once, an unknown folder answers an empty page, and the entry list paginates in
NAF after merging and ordering the feeds of the folder.

The repository ships a curated pack in `feeds/alfonso-articles.opml`: 18
validated feeds whose approved taxonomy is already in the outline trail, so the
import applies the organisation instead of adding flat subscriptions.
`feeds/README.md` records the taxonomy, the feed mapping, and the validation of
every feed. Import it with the intake route:

```bash
curl -X POST "$NAF_BASE_URL/api/v1/feeds/intake" \
  -H 'Content-Type: application/xml' \
  --data-binary @feeds/alfonso-articles.opml
```

`GET /api/v1/entries` accepts `published_after` and `published_before` as
ISO-8601 timestamps, which are read as UTC when they carry no zone and
combine with the other filters. The period is the basis for the reports that
cover "this week" or "since the last one".

The same route accepts `tags` as a repeated parameter, one tag per occurrence.
The reader combines them with AND, so every added tag narrows the list and an
entry must carry all of them; a request without `tags` applies no tag filter.
Send `?tags=security&tags=ai` to read the entries tagged with both.

The same route accepts `folder` as a repeated parameter. Each name is resolved
through the NAF-owned folders stored by the intake, never through the reader's
single category, so `?folder=Tech&folder=AI` selects the union of their feeds
and a feed kept under both is read once. The entries of the folder are merged,
ordered newest first, and paginated by NAF.

Every entry is projected onto the same shape in the list and in the single
read: `entry_id`, `guid`, `url`, `title`, `author`, the three dates, `status`,
`starred`, `content`, `reading_time`, `enclosures`, `tags`, and the feed's
`feed_id`, `feed_title`, `feed_url`, and `site_url`. The attachments and the
tags the feed provided are kept, so an audio enclosure is never lost on the
way to a report.

The three dates are distinct and never interchangeable. `published_at` is the
date the publisher declares, `created_at` is the date the reader first captured
the entry, and `changed_at` is the last known modification of the entry in the
reader. A date the reader does not report is `null` with the key still present,
so a consumer never has to tell a missing key from a missing value.

`POST /api/v1/collect` runs one ingestion pass with per-feed failure
isolation, and every pass is recorded in the NAF database as an ingestion run.
The response names the run, so a feed that starts failing leaves a trace of
which feed failed, when, and with what error. The optional `since` parameter
scopes the pass to entries published at or after that instant; a timestamp
without a zone is read as UTC, and an entry with no publication date is kept,
because an undated entry is never dropped. Pass the cutoff of the last report
to collect only what arrived after it.

The recorded history is readable through `GET /api/v1/ingestion-runs`, newest
first and paginated, with an optional `status` filter (`running`, `success`, or
`failed`) that lists the failed passes without reading a page of successful
ones. `GET /api/v1/ingestion-runs/{run_id}` returns one pass with its
`entries_count`, its per-feed `errors`, and a readable `error_summary`; an
unknown identifier answers 404 with the `INGESTION_RUN_NOT_FOUND` envelope. A
run still in `running` is served as recorded, with `finished_at` absent, so an
open pass is never read as a failure.

`GET /api/v1/metrics?days=7` builds the pilot snapshot for a window of 1–90 days
from the same NAF-owned rows plus the reader's feed list. The `sources` block
reports freshness and parsing state (a paused feed is counted but never read as
stale), `ingestion` aggregates the recorded passes, `reports` counts the stored
editions by status and measures their size and p50/p95 wall time, and `audio`
sums the assets. A reader failure leaves only `sources.available` false; the
other blocks still answer. The pilot that consumes this snapshot is
`docs/PILOT_PLAN.md`.

`GET /api/v1/feeds` and `GET /api/v1/feeds/health` return the same projected
shape: the identifier, the title, the feed and site addresses, the category,
the last check, the parsing errors, and the paused state. The reader's own
fields, such as its scraping rules, the credentials of an authenticated feed,
or its icon, never reach the API.

Deleting a subscription is destructive in the reader, and the response says so.
`DELETE /api/v1/feeds/{id}` removes the feed, and the reader cascades the
deletion to every entry that feed carried. NAF-owned records live outside the
reader and stay untouched, and no volume is affected. To stop following a feed
without losing its entries and their read state, pause it instead:
`PATCH /api/v1/feeds/{id}` with `{"disabled": true}` stops the polling and
keeps everything. The delete answer keeps `feed_id` and `removed` and adds a
`warning` that names the cascade.

## Reports

`POST /api/v1/reports` turns a selection of entries into a Spanish report with
citations, stores it, and returns the edition. The selection accepts a period
(UTC), feeds, categories, tags, a reader search, read/starred state, and
`since_last`, which starts after the newest saved cursor so nothing is reported
twice unless asked.

- Every story carries its claims and the citations that support them; the
  adapter fills each citation's URL, title, and author from the stored entry, so
  the model cannot invent them. One repair attempt is allowed before the edition
  fails with `502`.
- An empty selection answers `201` with `status: no_news` and an explicit
  Spanish message; it never recycles an older report.
- Each edition keeps its filters, the included entry ids, the model, the prompt
  version, and the cursor, which is what makes it reproducible.
- `GET /api/v1/reports` lists the history and `GET /api/v1/reports/{id}` returns
  the stories with their citations.
- The generator needs an OpenAI-compatible provider: `NAF_LLM_BASE_URL`,
  `NAF_LLM_API_KEY`, and `NAF_LLM_MODEL`. Without a model the routes answer
  `503 REPORT_GENERATOR_NOT_CONFIGURED` and the history stays readable.

`POST /api/v1/reports/{report_id}/audio` synthesizes the stored edition with
Kokoro ONNX and a Spanish voice, concatenates the segments into one mono 24 kHz
WAV, and stores it as an immutable asset. `GET /api/v1/reports/{report_id}/audio`
returns the file, and the report detail lists its duration, size, provider, and
voice. A second request returns the stored asset unless `force=true`; a
synthesis failure leaves the text edition intact and answers `502`.

## Classification and model tracking

`POST /api/v1/entries/{id}/classify` asks the configured model for a topic,
tags, publication type, and whether the entry is the creator's own announcement.
The answer is stored as an automatic suggestion, with a confidence, an explicit
uncertainty flag, and the models the entry names: name, creator, whether it is a
new model or an update, and a literal evidence quote. A quote that is not a
fragment of the entry is discarded.

`PATCH /api/v1/entries/{id}/classification` records the user's correction and
marks the row as `source=user`; a later automatic pass returns it unchanged.
`GET /classifications?review_needed=true` lists what the model could not place,
so nothing is force-fitted into a category.

`POST /api/v1/classifications/run` classifies a bounded batch (`limit` 1–20) of
the newest entries that have no stored classification. Corrected rows are never
revisited, and the first provider failure stops the pass while keeping what was
already stored, with a Spanish `stopped_reason`. The pending endpoint
(`GET /api/v1/classifications/pending?limit=20`) sizes the recent backlog
without walking the full reader history.

## Web interface

The same process renders the complementary screens the product plan requires
(decision 3, "web only"); it is not a second deployment, and the browser never
talks to Miniflux directly. The pages call the same `ReportService`,
`AudioService`, and reader adapter as the API.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Report history and the report creation form |
| `POST` | `/ui/reports` | Generate one report and redirect to its edition |
| `GET` | `/reports/{report_id}` | Report, citations, audio player, and synced transcript |
| `POST` | `/ui/reports/{report_id}/audio` | Synthesize the spoken edition and redirect back |
| `GET` | `/sources` | Feeds with their category and last check |
| `POST` | `/ui/classify` | Classify the newest pending entries and redirect to the sources page |
| `GET` | `/static/*` | Stylesheet and the vanilla-JS player |

The report page links every claim to its source, inlines the segments stored
with the audio asset, highlights the segment being spoken, and seeks when a
segment is selected. Spanish labels and messages are the only user-facing
text; a generation or speech failure re-renders the text edition without
leaking the provider detail. The API stores and serves every instant in UTC;
the pages render them in `NAF_DISPLAY_TIMEZONE` (default `UTC`) and append the
zone abbreviation, so a period reads in the deployment's local time without
changing the API contract. There is no framework and no build step.

## Documentation

- `docs/STANDARDS.md` — stack, layout, tooling, testing, and conventions.
- `docs/DEPLOYMENT.md` — topology, volumes, migrations, health, and rollback.
- `docs/PRODUCT_PLAN.md` — product specification, scope, and phased delivery plan.
- `docs/PILOT_PLAN.md` — Phase 6 cohort, readings, security, and go/no-go rules.
- `docs/PILOT_RESULTS.md` — the first pilot reading and its limits.
- `docs/DOCKER.md` — image shape, tag rule, and build verification.
- `feeds/README.md` — curated feed pack, taxonomy, and import.
- `CHANGELOG.md` — change history.
- `REMOTE.md` — local-only operational inventory (never tracked).

## License

Apache-2.0. See `LICENSE`.
