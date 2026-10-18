# feat(fase2): Phase 2 - Miniflux integration and collector

**Status:** `status::todo` | **Priority:** `priority::critical` | **Type:**
`type::feature` | **Source:** `source::user` | **Area:** `area::core`

**Part of Meta-Issue:** `naf#000` **Blocked by:** `naf#001`, `naf#002`

## Problem

Integrate Miniflux as the reader base via API. Implement minimal complement
layer for organizing/viewing in context of reports. Preserve all entries with
provenance; never duplicate Miniflux state.

## Affected Files & Locations

- `app/adapters/miniflux.py` (to create)
- `app/services/collector.py` (to create)
- `app/api/feeds.py`, `app/api/entries.py` (complement views)
- `docs/INTEGRATION_MINIFLUX.md` (to create)
- `tests/integration/` (Miniflux API contract tests with recorded fixtures)

## Evidence

- Plan: Fase 2, RF-01 to RF-06
- Decisions from #001

## Impact and Blast Radius

- Core ingestion path; must not break existing Miniflux setup
- API usage only; respect rate limits/timeouts

## Historical Context and Anti-Regression

- Idempotent operations; graceful degradation if source unavailable
- All entries preserved (no implicit filtering on ingest) - filtering only at
  report time

## Proposed Solution

1. **Miniflux API client**: auth, endpoints for feeds/entries/categories/marks,
   OPML, health
2. **Sync logic**: periodic sync (separate from report generation), track last
   sync, handle errors
3. **Provenance**: store reference to Miniflux feed/item IDs + original URLs
4. **OPML import/export**: verify roundtrip
5. **Dedupe**: by URL/GUID; related items grouped without removing originals
6. **Integration tests** with fixtures (recorded responses) or local Miniflux

## Acceptance Criteria

- [ ] Can list/add/test/pause feeds via integration
- [ ] Sync preserves all entries from feeds with origin/URL/dates
- [ ] OPML import/export works
- [ ] Search by metadata/content available
- [ ] Read/unread/favorites work
- [ ] Categories/collections supported
- [ ] Dedupe by URL/GUID; no loss of originals
- [ ] Errors visible, timeouts/backoff, partial failures don’t block others
- [ ] No DB access to Miniflux schema
- [ ] Documentation of integration
- [ ] Linked to meta #000, blocked by #001,#002
