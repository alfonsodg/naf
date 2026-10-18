# feat(fase0): Phase 0 - Decisions, validation, and integration proof

**Status:** `status::todo` | **Priority:** `priority::critical` | **Type:**
`type::feature` | **Source:** `source::user` | **Area:** `area::core`

**Part of Meta-Issue:** `naf#000` (aggregator with audio reports)

## Problem

Fase 0 is **blocking** per plan. Must confirm all decisions (section 17),
validate Miniflux as reader base, evaluate Podcastfy for audio, select test
feeds, and produce integration evidence before starting Fase 1.

## Affected Files & Locations

- `docs/PLAN_COLECTOR_NOTICIAS_IA_AUDIO.md` (section 17)
- `docs/DECISIONS.md` (to create)
- `docs/EVALUATION_MINIFLUX_PODCASTFY.md` (to create)
- `docs/FEEDS_TEST.md` (to create)
- `LICENSE` (confirm Apache-2.0)

## Evidence

- Plan sections 14 (Fase 0), 17 (decisions), 6 (sources), 8 (stack)
- Repo: minimal state, LICENSE present

## Impact and Blast Radius

- **Blocking**: All subsequent phases depend on these decisions.
- **Integration risk**: Miniflux API contract, Podcastfy integration
  feasibility.
- **Licensing**: Must confirm Apache-2.0 for product; inventory deps.

## Historical Context and Anti-Regression

- No prior work; decisions must be explicit (plan says "do not invent").
- Must exclude incompatible licenses from consideration.

## Proposed Solution

Complete all Fase 0 deliverables:

1. **Confirm decisions (10 items from section 17):**
   - Product name: naf (current) or confirm
   - Usage: individual private vs multiuser (recommend individual)
   - Interface: web only (recommend)
   - Categories/feeds/frequency; AI collection separate
   - Default duration/style + timezone
   - TTS: remote/local/both + cost/privacy + Spanish voice
   - Dev/test env + persistent audio storage
   - Retention for entries/transcripts/audio
   - Feedly API usage
   - Auto-send future (default no)

2. **Validate Miniflux integration:**
   - Test API (auth, feeds, entries, categories, read state, search, OPML
     import/export)
   - Confirm "use API only, never access tables"
   - Verify can preserve all entries with provenance

3. **Evaluate Podcastfy:**
   - Spanish quality (names, acronyms, numbers), segmenting, conversational
     style
   - Dependencies, licensing (Apache-2.0), local vs API, privacy
   - Compare against direct TTS fallback

4. **Select test feeds (5-10):** mix general + AI collection (OpenAI, Anthropic,
   Google DeepMind, Meta, Mistral, Hugging Face orgs, arXiv, etc.)

5. **License & deps:** confirm Apache-2.0; start dependency license inventory.

6. **Create docs** with reproducible evidence.

## Acceptance Criteria

- [ ] `docs/DECISIONS.md` created with all 10 decisions, rationale,
      approver/date
- [ ] `docs/EVALUATION_MINIFLUX_PODCASTFY.md` with API tests, pros/cons,
      recommendation per component
- [ ] `docs/FEEDS_TEST.md` with URLs, type, expected fields, verification notes
- [ ] LICENSE confirmed as Apache-2.0 (or justified change) - `LICENSE` file
      exists
- [ ] Dependency license inventory started (`docs/LICENSES.md` or section in
      eval)
- [ ] `REMOTE.md` reviewed if exists (or noted absence)
- [ ] Integration proof: can connect to Miniflux (or local setup) and read
      sample feeds
- [ ] Podcastfy Spanish samples tested and documented
- [ ] All evidence reproducible and linked
- [ ] Issue #001 (this) and meta #000 linked
