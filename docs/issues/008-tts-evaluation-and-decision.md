# feat(tech): TTS evaluation for Spanish with technical terminology

**Status:** `status::todo` | **Priority:** `priority::high` | **Type:**
`type::feature` | **Source:** `source::user` | **Area:** `area::audio`

**Part of Meta-Issue:** `naf#000` **Related to:** `naf#006`

## Problem

Need systematic TTS comparison for Spanish, focusing on model names (e.g., Qwen,
DeepSeek, LLaMA, Mistral), acronyms, numbers, anglicisms. Must decide between
Podcastfy (Apache-2.0) as conversational adapter vs direct TTS providers, with
fallback. No voice cloning in MVP.

## Affected Files & Locations

- `docs/TTS_EVALUATION.md` (to create, complement
  `docs/EVALUACION_STT_TTS_CLONACION_VOZ.md`)
- Test audio samples in `docs/samples/tts/` (to create)
- `app/adapters/tts/` design (from #006)

## Evidence

- Existing: `docs/EVALUACION_STT_TTS_CLONACION_VOZ.md`
- Plan sections 5,8,10,15

## Impact and Blast Radius

- Affects UX, cost, latency, privacy. Choice is architectural (pluggable).

## Historical Context and Anti-Regression

- Must test with realistic report excerpts (technical). Segment-based design
  allows swapping providers.
- Decision must be evidence-based with matrix.

## Proposed Solution

1. Create test corpus in Spanish with:

   - Model/family names, versions
   - Technical terms, acronyms
   - Numbers, dates
   - Mixed Spanish/English
   - Conversational transitions

2. Compare providers (local + remote as applicable). Consider: pronunciation,
   naturalness, pauses, speed control, API limits, cost, privacy, licensing.

3. Evaluate Podcastfy specifically (conversational script style vs direct TTS).

4. Produce matrix with scores, samples, recommendation.

## Acceptance Criteria

- [ ] Test corpus defined and documented
- [ ] Comparison matrix with all criteria (pronunciation, latency, cost,
      license, local/remoto)
- [ ] Audio samples generated and referenced
- [ ] Podcastfy tested end-to-end with Spanish sample
- [ ] Clear recommendation with justification
- [ ] Fallback strategy defined
- [ ] No voice cloning chosen for MVP
- [ ] Integrated into `docs/TTS_EVALUATION.md`
- [ ] Linked to #000 and #006
