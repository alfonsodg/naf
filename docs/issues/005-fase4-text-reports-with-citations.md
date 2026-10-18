# feat(fase4): Phase 4 - Text reports with citations and incremental selection

**Status:** `status::todo` | **Priority:** `priority::high` | **Type:**
`type::feature` | **Source:** `source::user` | **Area:** `area::core`

**Part of Meta-Issue:** `naf#000` **Blocked by:** `naf#001`, `naf#002`,
`naf#003`

## Problem

Generate on-demand Spanish text reports from selected entries (by period, feeds,
categories, tags, search). Must cite sources for every factual claim, use
cursor-based "since last", handle "no novedades", dedupe related stories.

## Affected Files & Locations

- `app/services/report_generator.py`
- `app/core/citation.py` (citation validation)
- `app/models/digest.py` (Digest, DigestStory)
- `app/api/reports.py`
- `docs/REPORTING.md`
- `tests/reporting/`

## Evidence

- Plan: Fase 4, RF-09 to RF-11, RF-13, RF-15
- Editorial rules section 4

## Impact and Blast Radius

- High editorial risk - must prevent unsubstantiated claims
- Citation integrity is critical

## Historical Context and Anti-Regression

- Reports are reproducible; each saved as immutable version (or with versioning)
- Cursor prevents re-inclusion unless explicitly requested
- Validation rejects segments without citations

## Proposed Solution

1. **Selection**: filters by period (UTC), feeds, categories, tags, search;
   support "since last" via cursor
2. **Dedupe/grouping**: group related coverage without losing originals
3. **Schema validation**: intermediate validated schema (story, claims,
   citations, uncertainties)
4. **Citation enforcement**: every factual claim must reference selected
   entries; validation checks
5. **Spanish output**: clear, attributed, distinguish official vs third-party
   for AI
6. **No novedades**: explicit message, no recycling
7. **History**: store digest with filters, included entries, version, timestamps
8. **Incremental**: cursor stores last digest point

## Acceptance Criteria

- [ ] Generate report from feed complete or filtered selection (RF-09)
- [ ] "Since last" uses saved cursor; no repeats unless requested (RF-10)
- [ ] Each story has links to original sources; citations present (RF-11)
- [ ] AI category distinguishes official vs third-party sources
- [ ] "No novedades" returns explicit message with no old content (RF-13)
- [ ] Duplicates grouped without removing entries
- [ ] Citations validated - rejects unreferenced factual claims
- [ ] Uncertainties marked; no invented data
- [ ] Report records filters, entries, version (RF-15)
- [ ] History of reports accessible
- [ ] Spanish text quality validated
- [ ] Linked to meta #000, blocked by #001,#002,#003
