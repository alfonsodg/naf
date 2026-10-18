# feat(fase1): Phase 1 - Contracts, architecture skeleton, and modular monolith

**Status:** `status::todo` | **Priority:** `priority::critical` | **Type:**
`type::feature` | **Source:** `source::user` | **Area:** `area::core`

**Part of Meta-Issue:** `naf#000` **Blocked by:** `naf#001`

## Problem

Define clean contracts between the Miniflux reader (via API) and our complement
layer (reports, classification, audio). Create a modular monolith skeleton that
can evolve without duplicating reader state.

## Affected Files & Locations

- `src/` or `app/` (to create)
  - `app/contracts/` - interfaces between components
  - `app/adapters/` - Miniflux API adapter, TTS adapter, LLM adapter
  - `app/core/` - domain models, citation/evidence rules
  - `app/services/` - report generation, classification, audio
  - `app/api/` - FastAPI endpoints for complement UI
- `tests/contract/`, `tests/unit/`
- `docs/ARCHITECTURE.md` (to create)
- `docs/CONTRACTS.md` (to create)

## Evidence

- Plan: section 8 (components, stack), 9 (data model), Fase 1

## Impact and Blast Radius

- Establishes boundaries: **never access Miniflux tables**, only API
- Enables testability and future extraction to workers if needed
- Core to evidence/citation system

## Historical Context and Anti-Regression

- Modular monolith to reduce complexity initially; interfaces allow later split
- Separation: reader state (Miniflux) vs complement state (digests, audio
  assets)

## Proposed Solution

1. **Architecture doc**: document modular monolith, components, boundaries, data
   ownership
2. **Contracts**: define interfaces (ports/adapters) for:

   - FeedReader (Miniflux API adapter) - read-only access
   - Classifier (LLM with structured output)
   - ReportGenerator (text with citations)
   - TTSProvider (segment-based, pluggable)
   - Storage (audio artifacts)

3. **Domain models**: Digest, DigestStory, AudioAsset, Citation, etc.
   (complement only)
4. **Project skeleton**: Python/FastAPI with `uv`, structure, config (typed),
   healthcheck
5. **Migrations**: complement DB schema (Postgres) separate from Miniflux's
6. **Contract tests** for adapters

## Acceptance Criteria

- [ ] `docs/ARCHITECTURE.md` with component diagram (text), boundaries, data
      ownership
- [ ] `docs/CONTRACTS.md` with interface contracts and invariants
- [ ] Skeleton app runs (`make dev` or `uv run ...`), health endpoint works
- [ ] Miniflux API adapter contract defined (no DB access to Miniflux)
- [ ] Complement data model defined (digests, stories, audio, citations)
- [ ] Initial migrations for complement DB (reproducible)
- [ ] Contract/unit tests for core types and contracts
- [ ] Config via typed settings (env-based), no secrets in repo
- [ ] Linked to meta #000 and blocked by #001

**Ref:** `naf#000` | **Blocked by:** `naf#001`
