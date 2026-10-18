# feat(fase3): Phase 3 - Classification (general + AI enrichment) and entities

**Status:** `status::todo` | **Priority:** `priority::high` | **Type:**
`type::feature` | **Source:** `source::user` | **Area:** `area::core`

**Part of Meta-Issue:** `naf#000` **Blocked by:** `naf#001`, `naf#002`,
`naf#003`

## Problem

Add classification for general categories and optional AI/model enrichment. AI
enrichment must distinguish official announcements from third-party/analysis and
mark uncertain items as "por verificar". Classifier must never hide or exclude
entries from the reader.

## Affected Files & Locations

- `app/services/classifier.py`
- `app/core/taxonomy.py` (types: general categories, pub types, AI
  classification)
- `app/models/creator_model.py` (optional entities with evidence)
- `docs/TAXONOMY.md`
- `tests/classification/`

## Evidence

- Plan: Fase 3, taxonomy (section 5), editorial rules (section 4)

## Impact and Blast Radius

- Editorial correctness critical for AI category
- LLM is not source of truth; must be conservative

## Historical Context and Anti-Regression

- Classifier failures must not block reading/ingestion
- Suggestions are corrigible; user changes preserved
- Separate general classification from AI-specific enrichment

## Proposed Solution

1. **Taxonomy**: configurable (not hardcoded closed list), multiple labels per
   item
2. **General classifier**: suggest topic/category/type; prefer "por revisar" on
   ambiguity
3. **AI enrichment**: detect launches/updates/papers/analysis; distinguish
   `official` vs `third-party`; require evidence for model attributes
4. **Entities**: `creator`, `model_entity` only with evidence or marked
   unverified
5. **Evaluation set**: labeled examples across categories + AI cases (launch vs
   update, official vs third-party)
6. **Safety**: never filter entries from reader based on classification

## Acceptance Criteria

- [ ] `docs/TAXONOMY.md` with general + AI taxonomy, types, labels
- [ ] Classifier suggests but never auto-excludes
- [ ] AI classification distinguishes official/third-party; uncertain marked
      "por verificar"
- [ ] Model attributes require evidence or marked unverified (RF-08)
- [ ] Corrections preserved (user can override)
- [ ] Evaluation metrics on test set; conservative on ambiguity
- [ ] Works even if LLM unavailable (degrades gracefully)
- [ ] No impact on ingestion/read paths if classifier fails
- [ ] Linked to meta #000, blocked appropriately
