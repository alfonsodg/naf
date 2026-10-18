# feat(core): Implement news aggregator with categorized feeds and on-demand audio reports

**Status:** `status::todo` | **Priority:** `priority::critical` | **Type:**
`type::feature` | **Source:** `source::user` | **Area:** `area::core`

## Problem

The project needs to build a categorized news/feed aggregator that can generate
Spanish text and audio reports on demand (inspired by NotebookLM's Audio
Overview). The plan is documented in `docs/PLAN_COLECTOR_NOTICIAS_IA_AUDIO.md`.

Key requirements:

- General-purpose feed reader (not limited to AI) with user-defined
  categories/collections
- On-demand generation of Spanish text+audio reports; ingestion independent of
  generation
- Strong evidence/citation requirements (every factual claim must link to
  sources)
- Special handling for AI/model announcements (distinguish official vs
  third-party)
- Reuse OSS where possible: Miniflux (Apache-2.0) as reader base, Podcastfy
  (Apache-2.0) for conversational audio
- Individual use (MVP), no multi-user, no automated distribution

## Affected Files & Locations

- `docs/PLAN_COLECTOR_NOTICIAS_IA_AUDIO.md` - Full specification
- New modules under planned structure (to be defined in Fase 1):
  - `app/` or `src/` for application code
  - `docs/` for design/decisions
  - `tests/` for validation

## Evidence

- Plan: `docs/PLAN_COLECTOR_NOTICIAS_IA_AUDIO.md` (sections 1-19)
- Existing repo state: minimal (README, LICENSE, docs only)
- Remote: `origin git@github.com:alfonsodg/naf.git`

## Impact and Blast Radius

- **Users**: Individual user initially (MVP scope)
- **Scope**: Full application - ingestion, storage, classification, report
  generation, TTS, UI
- **Dependencies**: Miniflux (Apache-2.0), Podcastfy (Apache-2.0), PostgreSQL,
  FastAPI/Python stack
- **Cross-cutting**: Licensing (Apache-2.0 target), security (SSRF prevention),
  editorial rules for citations

## Historical Context and Anti-Regression

- This is a greenfield project in `naf`. No prior implementation.
- Must not fork incompatible licenses (e.g. AI Summary Podcast CC BY-NC 4.0) -
  explicitly excluded in plan.
- Plan phases 0-6 define incremental delivery to minimize regression risk.
- Evidence/citation rules are central to prevent hallucinations.

## Proposed Solution

Implement in phases as specified in the plan:

1. **Fase 0**: Confirm decisions (section 17), validate Miniflux+Podcastfy
   integration, select feeds, establish issue baseline.
2. **Fase 1**: Define contracts between reader (Miniflux API) and our extension
   layer; create modular monolith skeleton.
3. **Fase 2**: Integrate Miniflux as reader base; implement minimal complement
   for reports/audio.
4. **Fase 3**: Add classification (general + AI enrichment) with "por verificar"
   on uncertainty.
5. **Fase 4**: Text report generation with citations and cursor-based
   incremental selection.
6. **Fase 5**: Audio generation via TTS comparison (no voice cloning in MVP);
   segment-based synthesis.
7. **Fase 6**: Pilot with 8-15 feeds, hardening, go/no-go.

This meta-issue coordinates child issues for each phase and key components.

## Acceptance Criteria

- [ ] **Phase 0 complete**: All 10 decisions from section 17 documented and
      approved; Miniflux+Podcastfy integration validated; feeds list selected;
      LICENSE confirmed.
- [ ] **Reader integration**: Can browse feeds via Miniflux integration (API),
      preserving all entries with provenance.
- [ ] **Categorization**: User-defined categories/collections work; filters
      combinable.
- [ ] **Text reports**: On-demand reports with citations; each factual claim
      links to source; cursor-based "since last" works; explicit "no novedades"
      when empty.
- [ ] **Audio reports**: Segment-based TTS, downloadable audio, player with
      transcript sync, references accessible.
- [ ] **Evidence rules**: AI announcements correctly distinguished (official vs
      third-party); uncertain items marked "por verificar".
- [ ] **Security**: SSRF protections, timeouts, domain allowlists, safe handling
      of external content.
- [ ] **Documentation**: Decisions, contracts, setup/run instructions
      documented.
- [ ] **Pilot validated**: Fase 6 complete with evidence and go/no-go
      recommendation.

**Part of:** This is the coordinator meta-issue. Child issues will be created
for each phase.
