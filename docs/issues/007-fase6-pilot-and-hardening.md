# feat(fase6): Phase 6 - Pilot with 8-15 feeds, hardening, and go/no-go

**Status:** `status::todo` | **Priority:** `priority::high` | **Type:**
`type::feature` | **Source:** `source::user` | **Area:** `area::core`

**Part of Meta-Issue:** `naf#000` **Blocked by:** `naf#001`-`naf#006`

## Problem

Run pilot with 8-15 feeds (mix general + AI/model feeds). Validate ingestion
completeness, citations, audio, security, costs. Produce evidence and go/no-go
recommendation.

## Affected Files & Locations

- `docs/PILOT_PLAN.md` (to create)
- `docs/PILOT_RESULTS.md` (to create)
- `docs/SECURITY_CHECKLIST.md` (to create)
- `docs/METRICS.md` (to create)

## Evidence

- Plan: Fase 6, pilot conditions (16), metrics (16)

## Impact and Blast Radius

- Validation of all acceptance criteria from meta
- Security hardening critical

## Historical Context and Anti-Regression

- Must meet all pilot acceptance conditions:
  - Each factual claim has primary source or explicitly secondary-only
  - No classifying third-party as official launch
  - "Since last" doesn't repeat without explicit action
  - Source failure doesn't block others; visible
  - Audio failure leaves text available; retryable without redoing stories
  - User sees period/filters/time/version

## Proposed Solution

1. **Pilot plan**: feed list (8-15), period, scenarios (full, filtered,
   since-last, multi-category, AI-specific)
2. **Metrics**: success rate per source, availability % (no filtering loss),
   classification accuracy (general + AI), citation validity %, duplicate rate,
   report/audio success, p50/p95 latency, cost per report (text+audio), Spanish
   quality, duration vs target
3. **Security**: SSRF (allowlists, block private nets, redirect validation),
   timeouts, size limits, MIME, prompt injection hardening, secrets handling, no
   external content execution
4. **Pilot execution**: run agreed period, collect evidence (samples)
5. **Go/no-go**: document findings, blockers, recommendations

## Acceptance Criteria

- [ ] `docs/PILOT_PLAN.md` with feeds, scenarios, success criteria
- [ ] `docs/SECURITY_CHECKLIST.md` covering SSRF, timeouts, redirects, secrets,
      content safety
- [ ] Pilot run with evidence for each scenario
- [ ] `docs/PILOT_RESULTS.md` with metrics against baseline (or initial values)
- [ ] All pilot conditions met (see problem)
- [ ] Cost/latency measured realistically
- [ ] Spanish pronunciation and citation UX acceptable
- [ ] Issues found logged (or closed if fixed) with evidence
- [ ] Go/no-go recommendation with rationale
- [ ] Linked to meta #000, blocked by all prior phases
