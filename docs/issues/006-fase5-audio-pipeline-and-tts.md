# feat(fase5): Phase 5 - Audio pipeline, TTS evaluation and segment-based synthesis

**Status:** `status::todo` | **Priority:** `priority::high` | **Type:**
`type::feature` | **Source:** `source::user` | **Area:** `area::core`

**Part of Meta-Issue:** `naf#000` **Blocked by:** `naf#001`, `naf#002`,
`naf#003`, `naf#005`

## Problem

Generate Spanish audio from validated text reports. Must evaluate TTS providers
(Spanish quality, names/acronyms/numbers, latency, cost, license/privacy). No
voice cloning in MVP. Use segment-based synthesis for resilience and
repairability.

## Affected Files & Locations

- `app/services/audio_generator.py`
- `app/adapters/tts/` (base + providers: Podcastfy adapter, fallback direct TTS)
- `app/core/audio.py` (segmentation, merging)
- `app/models/audio_asset.py`
- `docs/TTS_EVALUATION.md` (builds on existing
  docs/EVALUACION_STT_TTS_CLONACION_VOZ.md)
- `tests/audio/`

## Evidence

- Plan: Fase 5, RF-12, audio design in sections 8/10
- Existing: `docs/EVALUACION_STT_TTS_CLONACION_VOZ.md` (may inform comparison)

## Impact and Blast Radius

- Cost/latency can be significant; need caching and on-demand
- Audio artifacts storage; retention considerations

## Historical Context and Anti-Regression

- Segment-based: fail only bad segment, retry independently (section 10)
- Audio is immutable once generated; regeneration explicit and versioned
- If audio fails, text report remains available (requirement in pilot)
- Podcastfy integration considered but must prove quality before adoption

## Proposed Solution

1. **TTS comparison matrix** (Spanish-specific): intelligibility of technical
   names/models, acronyms, numbers, anglicisms, pauses, conversational style,
   latency, cost, local/remoto, licensing/conditions. Document decision with
   justification.
2. **Integrate Podcastfy** as pluggable adapter if meets criteria (Apache-2.0).
   Fallback to direct TTS.
3. **Segment-based synthesis**: intro, stories, transitions, closure; merge with
   metadata; handle chunking if provider limits.
4. **Storage**: abstract interface (local first, pluggable for deployment)
5. **Player + transcript**: sync with text segments, citations accessible,
   download
6. **Caching/versioning**: immutable audio assets, checksum, duration,
   provider/voice/model
7. **Resilience**: partial failure allows retry of segments only; text never
   lost

## Acceptance Criteria

- [ ] `docs/TTS_EVALUATION.md` with comparison matrix, test samples (Spanish
      technical terms, model names), recommendation + justification
- [ ] Decision documented (Podcastfy vs direct TTS) with evidence
- [ ] TTS provider abstraction (pluggable)
- [ ] Segment-based generation works; failed segment retryable
- [ ] Audio stored, playable, downloadable (RF-12)
- [ ] Transcript sync with audio segments
- [ ] References/citations accessible from player
- [ ] Audio failure leaves text report available; can retry without regenerating
      text
- [ ] Immutable artifacts with versioning (regenerate only explicit)
- [ ] Duration/size/checksum tracked
- [ ] No voice cloning in MVP
- [ ] Linked to meta #000, blocked appropriately
