# Product Plan: Categorized Feed Aggregator with Audio Reports

| | |
|---|---|
| **Project** | naf — Categorized feed aggregator with audio reports |
| **Version** | Unreleased |
| **Created** | 2026-10-18 |
| **Updated** | 2026-10-18 18:00 |
| **Author** | Alfonso de la Guarda Reyes |
| **Location** | `docs/PRODUCT_PLAN.md` |

**Status:** functional and technical proposal handed to a development agent
**Date:** 2026-10-18
**Product language:** Spanish
**Target license:** open source, with an OSI-approved license; initial
recommendation: Apache-2.0 (pending owner confirmation)
**Goal:** build a general-purpose categorized feed reader that collects entries
from integrated sources and can generate reports in Spanish, as text and audio,
when the user requests them.

## 1. Executive summary

Build a general-purpose feed reader inspired by Feedly, with user categories and
collections, plus audio reports in the style of NotebookLM's Audio Overview.
Every entry available from integrated sources is kept as a navigable, searchable
item; the user decides which sources, period, categories, or topics to include in
each report. Periodic ingestion is independent from generation: reports and audio
are generated on request, unless explicit scheduling is enabled in the future.

Verifiable tracking of AI model releases is a specialized use case and a
high-value category, not the limit of the product. In that category the system
identifies creator, announcement, date, change type, and primary source; the
remaining categories use the general reading and summarization flow.

The review confirms that starting from scratch is not advisable: OSS readers
already solve much of ingestion, categorization, and reading; audio projects
already automate synthesis and TTS. The application should reuse those pieces and
add selective reports with provenance. Model announcement tracking is a
specialized enricher inside the general catalog, not a standalone product.

## 2. Problem and users

### Problem

Information of interest is scattered across feeds on many topics. The user needs
to follow heterogeneous subscriptions by category, review what is new in one
place, and request a spoken summary without losing access to the original
content. For AI, the user additionally needs to distinguish official
announcements from commentary and from updates to existing releases.

### Initial user

A person who integrates feeds across several topics, organizes them, and wants to
read them in one place or request a Spanish report to listen to and open the
sources. AI/models is an initial use case, not an exclusive one. Design first for
a single individual user; do not assume multi-user accounts or public publishing.

### Main tasks

1. Add feeds individually or import subscriptions; organize them into
   categories/collections and browse all their entries.
2. Explore by date, source, category, search, and read state.
3. Request reports such as "the important technology news this week" or "AI/model
   news since my last report".
4. Read or listen to the result and open sources; adjust categories, sources, and
   report duration/style.

### 2.1 Similar products and projects reviewed

Documentary review of repositories and public documentation as of 2026-10-18; it
is not equivalent to an installation, code audit, or functional test.
Capabilities and licenses must be re-verified before adopting a dependency.

| Project | What it solves today | Overlap and gap for this product | Initial assessment |
| --- | --- | --- | --- |
| [AI Summary Podcast](https://github.com/applab-nl/ai-summary-podcast) | Integrated pipeline: RSS/web, LLM summarization, deduplication, composition, TTS, dashboard, history, and an RSS feed of episodes with links. | A close precedent for the spoken newsletter, but not for the general reader or for verifying official announcements. It does not certify Spanish quality. | Functional reference; CC BY-NC 4.0 is incompatible with the target open source license. |
| [Daily Digest](https://github.com/MarcelloMorettoni/daily-digest) | Newsletter configurable by category and RSS/YouTube sources, local Ollama, local Piper, interface, history, and scheduling. | Very close in experience and useful as a local execution reference; its README presents it as a daily newsletter, not as an auditable record of official announcements or a full Feedly-style reader. | Design/prototype reference, not a production base without review: the observed page shows a single commit and exposes no license in the repository listing. Do not assume reuse rights. |
| [Podcastfy](https://github.com/souzatharsis/podcastfy) | Python library/API that turns sets of sources into multilingual audio conversations and allows customizing script/style. Declares Apache 2.0. | Covers conversational generation; it is not a persistent reader, category/read manager, or history of all entries. | Candidate as the audio report engine, not as a complete application; validate technical Spanish. |
| [Miniflux](https://github.com/miniflux/v2) | Mature RSS/Atom/JSON Feed reader with categories, search, read state, REST API, and PostgreSQL; Apache 2.0. | Covers the base of a categorized reader and can avoid rebuilding polling, reading, organization, and search from scratch. It provides no audio reports and no specialized model category. | Preferred candidate for the reader base; validate the API and whether its UI is reused or a complementary interface is built. |
| [FreshRSS](https://github.com/FreshRSS/FreshRSS) | Self-hosted, multi-user aggregator with an API, WebSub, and basic XPath extraction for sites without feeds; AGPL-3.0. | A general reader alternative, but it solves neither audio reports nor editorial analysis. | An option if WebSub/extraction are decisive; review AGPL obligations before distributing an integration or modifications. |
| [RSSHub](https://github.com/DIYgod/RSSHub) | Generates RSS feeds from maintained routes for various sites and services. | Can cover sources without native RSS; it is discovery/normalization infrastructure, not a reader, classifier, or audio generator. Coverage depends on the specific route and can break if the site changes. | Use only as an optional self-hosted adapter and only after reviewing/measuring each route. Prioritize native official sources and APIs; never treat the output of a community route as confirmation from the creator. |
| [Feedly](https://feedly.com/) | Commercial product for reading, organizing, and analyzing sources. | Functional reference for the general aggregator; its API/commercial plan is not a requirement if Miniflux is reused. | Experience benchmark, not a dependency of the open source core. |
| [NotebookLM / Gemini Notebook](https://support.google.com/gemininotebook/answer/16212820?hl=en) | Generates conversational Audio Overviews from sources, with playback, citations, and download from the application. | A reference for the listening experience and source presentation, not a continuous feed collector, and no backend API is assumed for automation. | UX inspiration; generate the content through an own pipeline or a proven TTS/Python library. |

### Reuse conclusion

- **Priority reuse for the open source product:** integrate Miniflux (Apache-2.0)
  as the RSS/Atom feed engine and evaluate Podcastfy (Apache-2.0) as the
  script/conversational audio component. Review dependencies, attribution
  notices, security, and compatibility before pinning versions or distributing.
- **Own code limited to the differentiator:** report orchestration by category,
  incremental cursor, unified provenance, and, as an optional enricher, a catalog
  of creators/models and the distinction between official and third-party
  announcements. Do not build an RSS reader or a generic conversational generator
  if the existing OSS components satisfy the criteria.
- **AI Summary Podcast:** do not incorporate it or fork it as a base. Its
  published license is CC BY-NC 4.0; OSI requires a license that does not restrict
  fields of use, including commercial use. It may serve as a functional
  reference, but its code does not enter an open source distribution that permits
  commercial use without permission or a license change granted by the rights
  holders.
- **Daily Digest:** interface/flow reference until the repository has a clear
  license and sufficient maintenance; do not copy unlicensed code.
- **FreshRSS:** an aggregation alternative, but Miniflux is preferable for the
  initial design; FreshRSS uses AGPL-3.0 and its obligations must be reviewed
  before distributing an integration or modification.
- **RSSHub:** fallback only for sources without a native feed/API, after verifying
  each route; it does not prove authorship of the announcement.
- Feedly and NotebookLM are product references or external integrations, not
  dependencies of the open source core.
- **Immediate rejection criteria:** license incompatible with the intended use;
  inability to run locally/isolated as required; lack of source traceability;
  unacceptable technical Spanish; an integration that forces exposing
  data/credentials without approval.

## 3. MVP scope

### Included

- General categorized reader: individual additions and OPML import, categories
  and collections, read/unread, save/favorites, search, and chronological feed.
- Periodic ingestion of every entry and metadata each integrated source provides,
  without restricting topics to AI. If the feed only offers title/excerpt, keep
  that level; full-body extraction depends on the source.
- Initial sources from several areas as configurable examples, not as a closed
  list of accepted sources.
- User-defined categories/collections, manual assignment, and correctable
  automatic suggestions; combinable filters by source, date, category, tags,
  search, and read state.
- Report requests over every entry matching period, source, category, tags, or
  search; do not filter by AI by default.
- Entry record with URL, dates, available content, category, state, and a
  reference to the originating feed.
- Duplicate grouping as a reading aid, without removing original entries or
  hiding that there are several publications.
- Optional enricher for AI/models: detect releases, updates, creators, and primary
  evidence.
- Reuse the reader interface/services for RSS tasks; add a lightweight own screen
  to request reports, listen, review sources, and browse history.
- Spanish script with links and attribution to sources. For AI, official
  announcement, research, and third-party analysis are distinguished.
- Spanish audio synthesis by blocks, player, and file download; transcript
  synchronized with or attached to the audio.
- Report history and the ability to replay them without regenerating the audio.
- Ingestion error log and bounded retries.

### Outside the MVP

- Automatic delivery by email, Telegram, custom RSS, or push notifications. The
  on-demand report is validated first.
- Scraping social networks with authentication or account automation.
- Full reproduction of articles, full translation, or storage of complete copies
  without a reviewed legal/licensing basis.
- Comments, multi-user collaboration, social recommendations, or
  popularity-based ranking.
- Training/fine-tuning of own models.
- Replicating Feedly or NotebookLM's proprietary interface, brand, or content.

## 4. Editorial and evidence rules

1. Preserve author, original source, and link in every category; never present a
   generated summary or classification as the author's original text. For the AI
   category, prioritize the creator's announcement/documentation and then
   distinguish papers, third-party coverage, and analysis.
2. Every concrete statement in the report must point to one or more stored
   sources. The player must offer access to the source list, and the text report
   must link them next to the relevant points.
3. For the AI category, do not claim a model is "new" merely because the
   repository was updated. Differentiate `new_model`, `model_update`,
   `weights_release`, `API_release`, `research_paper`, `product_update`,
   `analysis`, and `other`.
4. Store separately the date declared by the publisher, the first-capture date,
   and the last known modification date. Show a timezone, or a date without a
   time, when the source does not allow resolving it.
5. Automatic extraction proposes classification and entities; a low score or a
   date conflict must appear as "to be verified", and must never be resolved by
   inventing data.
6. In text/audio, distinguish "the creator claims" from independent results. Do
   not infer benchmarks, license, languages, size, availability, or weights that
   the source does not confirm.
7. Do not synthesize a list of titles without context: include what changed, who
   it matters for, and known limitations, without adding unattributed opinion.
8. Store metadata, links, and brief excerpts as needed; avoid copying the full
   body of articles by default. Review terms/licenses before enabling extensive
   extraction or redistribution.

## 5. Initial taxonomy

Categories must be editable, not hard-coded as a closed list. AI areas are a
suggested taxonomy, not the total thematic scope.

### Suggested initial general categories

- Technology and software.
- Science and research.
- Business and economics.
- Politics, regulation, and security.
- Health, education, culture, and media.
- User-defined custom categories.

### Publication types

- News/article.
- Announcement or press release.
- Research/paper/preprint.
- Product/service launch or update.
- Analysis, opinion, or commentary.
- Podcast, video, or other audio/video attachment.
- User-defined custom type.

### Specialized AI/model classification

- Model/family release; update; weights/API publication.
- Research/paper, evaluation/benchmark, or technical report.
- AI-based tool/platform.
- AI policy, safety, or regulation.
- Third-party analysis, separated from the creator source.

### Areas/models

- LLMs and reasoning.
- Open models/available weights.
- Vision, VLM, and documents/OCR.
- Audio: speech, STT, TTS, and music.
- Video and generative image.
- Agents and tool use.
- Embeddings and search.
- Robotics/physical world.
- Science and specialized models.

Each item may carry several tags. Keep the editorial category separate from the
model type; for example, a weights announcement for an audio model carries both
dimensions.

## 6. Initial sources and discovery strategy

Do not limit the application to a list of labs. The user can add feeds on any
supported topic. The initial example/test package must mix several general
categories with an AI/models collection; it may include news, blogs, research,
official launches, and repository releases. AI collection candidates: OpenAI News,
Anthropic News, Google DeepMind News, Meta AI, Mistral AI, Microsoft Research/AI,
NVIDIA Research, official Qwen and DeepSeek repositories, the Hugging Face
organizations of the creators, and arXiv. This list is editable and does not limit
admission. Verify URL, source type, and method before incorporating them.

### Capture preference order

1. Official RSS/Atom.
2. Public/documented owner API.
3. Activity/release feed of the official repository (for example, GitHub Atom
   when applicable).
4. Official-page adapter with bounded extraction, reviewed terms, respect for
   published crawling rules, rate limits, caching, and `ETag`/`Last-Modified` when
   the server provides them.
5. Manual entry approved by the user when the source is not automatable.

The product must import/export OPML for feed catalog portability. Category
configuration and read state are product data and must persist even if a source
becomes unavailable.

Hugging Face can detect new/updated model repositories per organization through
the Hub API/webhooks, but this is a discovery signal, not sufficient proof that it
is a public announcement from the creator. The official article or card must be
verified before labeling a release.

Feedly remains an optional integration. It is not an MVP dependency: its API
requires enabled access/a plan, and additional features may have their own
requirements. Do not base the design on a private API, and do not reuse content
without confirming the current terms.

## 7. Functional flow

```text
Registered sources
  -> scheduled polling and adapters
  -> keep every entry available in each feed
  -> normalize + organize into categories/read state
  -> search and reading of the full catalog
  -> user request (full feed or period + categories + preferences)
  -> entry selection by filters/cursor
  -> Spanish script with links to sources
  -> optional specialized enrichment for AI/models
  -> citation/claim validation
  -> TTS synthesis by segments
  -> reproducible edition: text + audio + sources
```

Periodic monitoring is independent from delivery. Do not filter entries during
ingestion by relevance, category, or LLM score; every item is kept in the reader,
and only the report applies the user's selection. If the selection contains
nothing new, report "no news" without recycling content. Store the report cursor
so that "since the last one" is deterministic; allow re-execution and preserve
script versions.

## 8. Recommended technical design

The architecture must start as a **modular monolith** to reduce cost and
complexity. Separate internal interfaces so workers can be extracted later.

### Components

1. **User experience:** initially reuse the Miniflux UI/API to manage feeds, read,
   search, and organize; add a small complementary application to launch reports,
   show citations, and play audio. Do not build a second complete reader in the
   MVP.
2. **Source/adapters catalog:** a common contract to run a query, return
   normalized entries, and report errors/retries.
3. **Scheduler/worker:** periodic ingestion and asynchronous report/audio tasks.
   Do not run long crawls inside the HTTP request.
4. **Relational persistence:** connections/feeds, entries, categories, tags, read
   state, runs, and report editions; creator/model entities are an optional
   extension of the general domain.
5. **Audio storage:** an abstract interface for local storage during development
   and approved persistent storage in deployment.
6. **LLM layer:** interchangeable adapter for extraction/classification and
   synthesis with structured output and schema validation. The model is not a
   source of truth.
7. **TTS layer:** interchangeable adapter, segmentation, audio join, metadata,
   and duration. Do not pin a provider/voice before a reproducible Spanish
   comparison.
8. **Observability:** structured logs, failure/duration metrics, and traceability
   by `source_id`, `ingestion_run_id`, and `digest_id`; never log keys or
   unnecessary full bodies.

### Reference stack with priority OSS reuse

- **Own domain:** a Python/FastAPI backend with `uv` is the recommended initial
  option to integrate the reader, generate reports, keep provenance, and add
  domain extensions (such as model tracking). It must not re-implement the general
  catalog if the chosen OSS reader already provides it. The UI consumes the reader
  and the report component.
- **RSS/UI:** reuse Miniflux as the main reader (interface and service) to manage,
  read, search, mark, and organize feeds; the own application is complementary and
  focused on reports/audio. Integrate through the documented API, never by
  accessing its tables. If article-level categories or collections are missing,
  add only that thin layer in the complement. Sources without native feeds/APIs
  use small adapters; RSSHub remains a fallback.
- **Persistence:** PostgreSQL for domain data. If Miniflux is adopted, its internal
  database is owned by Miniflux; do not access its tables directly. Document both
  databases and their backups before integration.
- **Audio:** integrate Podcastfy as the Python adapter for conversational Spanish
  script, subject to a test of technical quality, privacy, API, and dependencies.
  Do not re-implement that stage if it meets the requirements. Keep direct TTS by
  segments only as a fallback for a demonstrated shortcoming. Podcastfy does not
  replace ingestion, verification, or the product history.
- Worker/scheduler in the same project for the MVP; responsive web frontend;
  persistent object storage for audio; and a modular architecture, not premature
  microservices.
- Evaluate the options of the existing study referenced by the source material; do
  not pin voice/provider until measuring pronunciation of model names, acronyms,
  figures, and anglicisms in Spanish. That study is not part of this repository.

This stack is a recommendation for estimation, not an authorization to deploy or
to install services locally. The new project must decide its environment and
document it before any integrated test.

The product repository must declare an OSI-approved license. Apache-2.0 is
proposed; confirm before creating the `LICENSE` file. Maintain an inventory of
licenses for dependencies, models, voices, prompts, datasets, and assets: the fact
that the code is OSS does not automatically make those materials open source.

## 9. Minimum data model

- `feed_connection`: URL/identifier, title, site, format, securely referenced
  credentials, sync state, cursor, and polling metadata. Miniflux may own this
  entity if it is chosen as the reader.
- `item`: originating feed, canonical GUID/URL, title, author, dates, language,
  content exactly at the available level, attachments, fingerprint, and state.
- `category`, `collection`, `tag`, and relations: user taxonomy/folder and
  multiple assignments; OPML import/export maintains feeds, without forcing a
  merge of private engine preferences.
- `reading_state`: read/unread, saved/favorite, and change timestamp.
- `item_relation`: duplicate or related coverage; relations do not delete
  individual entries nor replace access to the original.
- `creator` and `model_entity`: optional extension for the AI category; attributes
  only with evidence (modality, weights, license, languages, parameters, context).
- `ingestion_run`: start/end, counts, summarized errors, state, and adapter
  version.
- `digest`: time range, filters, cursor, format, language, target duration, state,
  and prompt/model version.
- `digest_story`: order, inclusion reason, summary, claims, and sources.
- `audio_asset`: format, duration, size, checksum, voice/provider/model, state, and
  storage URI.

Deletions and retention must be explicit and configurable. Classification changes
preserve enough history to audit reports already generated.

## 10. Report and audio generation

1. Resolve the period with UTC dates and display it in the user's local timezone.
2. Select items not yet seen for that cursor; allow including read or older items
   through an explicit option.
3. Group repeated coverage by entity/release and show several sources without
   repeating the same story.
4. Create a validated intermediate schema: title, summary, relevance, type,
   creator, date, claims, uncertainties, and references.
5. Generate a script of configurable target duration (suggested initial value:
   5-8 minutes), prioritizing quality/provenance over filling an artificial
   duration.
6. Verify that every factual statement in the script references a selected entry;
   reject or flag unsupported segments.
7. Synthesize by segments (introduction, story, transition, closing) to retry only
   the failed segment. Add pauses and pronunciation of technical names through an
   editable dictionary.
8. Store text, references, and audio as an immutable edition; regenerate only
   through explicit action and store the new version.
9. If the text exceeds the TTS provider limits, segment it without truncating or
   silently altering the content.

NotebookLM's Audio Overview is a UX reference, not a backend dependency: its
documentation describes generation from sources, playback, citations, and download
inside Gemini Notebook. Do not assume a public automation API. The product must be
able to operate with its own pipeline.

## 11. Verifiable functional requirements

- **FR-01 Feeds:** the user can add, test, pause, and delete a subscription; view
  health, last sync, and errors.
- **FR-02 Portability:** OPML import/export preserves the feed list; failures in
  one source do not block importing or syncing the others.
- **FR-03 Full capture:** every entry delivered by integrated feeds is shown and
  kept, with origin, URL, and dates, with no implicit thematic filtering. Limits of
  the content published by the feed are visible.
- **FR-04 Organization:** user categories/collections and tags allow multiple
  assignment and combinable filters. Read/unread and save/favorite can be set.
- **FR-05 Search:** search text in entry metadata and available content, respecting
  the content level provided by each source.
- **FR-06 Dedupe:** the same URL/GUID does not duplicate records; similar stories
  are grouped as related without deleting any entry.
- **FR-07 Classification:** optional automatic classification can suggest topic and
  tag; the user corrects it and their changes are preserved.
- **FR-08 AI evidence:** model attributes link to evidence or are explicitly marked
  as unverified.
- **FR-09 On-demand report:** generate a report over the full feed or a selection
  by period, feeds, categories, tags, and search; do not impose the AI category by
  default.
- **FR-10 Incrementality:** "since the last one" uses the stored cursor and does not
  repeat items unless the user requests it.
- **FR-11 Text and citations:** every story offers links to the original
  feed/entry and preserves authorship; the AI category distinguishes official from
  third-party sources.
- **FR-12 Audio:** a ready edition can be played/downloaded and keeps correspondence
  with the transcript version and references.
- **FR-13 No news:** return an explicit message without generating filler or
  repeating old content.
- **FR-14 Failures:** timeout, invalid response from a source, LLM error, or partial
  TTS failure are shown with a recoverable state and without duplicating tasks.
- **FR-15 Reproducibility:** every report records filters, included entries,
  generator version, and audio state.

## 12. Non-functional requirements and risks

- Idempotent ingestion, with timeouts, per-domain limits, backoff, and respect for
  the access policies published by each source.
- Every external operation must be disableable per source/configuration.
- Do not store credentials in the repository; secrets only through the environment's
  documented mechanism.
- SSRF protection: allow only authorized schemes/hosts, block private networks, and
  revalidate DNS/HTTP redirects before downloading.
- Limit size, MIME, redirects, and download time; do not execute content from
  sources.
- Treat article text as untrusted input; block instructions embedded in sources
  that attempt to change agent behavior.
- Citations and links must survive model errors; output is not published outside
  the authenticated user in the MVP.
- Retention limited to metadata, excerpts provided by the source, and the generated
  audio that is needed. Review copyright, terms, and privacy before extensive
  extraction or external delivery.
- Measure per report: estimated/actual LLM and TTS cost, generation duration, valid
  citation rate, failures per source, audio size, and Spanish quality.
- Main risk: announcements without RSS or with dynamic content; mitigation:
  controlled adapters, change detection, manual fallback, and a source health
  monitor.
- Editorial risk: confusing a weights update with a new model, or taking a
  promotional claim as an independent evaluation; mitigation: visible taxonomy and
  provenance.
- Audio cost/latency risk: synthesize on demand, cache immutable editions, and allow
  text without audio when the user chooses.

## 13. Planned interface

1. **Home/Feed:** general reader with lists by source/category/collection, search,
   date range, read/unread, saved items, and reading actions.
2. **Entry detail:** content available from the feed, attachments, author, date,
   original link, tags, and related sources. For AI, add model evidence and
   official/third-party status when applicable.
3. **Create report:** full feed or filters by period (including "since the last
   one"), category, source, tag, or search; indicative duration, style, and audio
   selector.
4. **Report:** player, transcript by segments, citations per story, download, filters
   used, and generation time.
5. **Sources:** name, URL, method, categories, last query, errors, and controls to
   pause/test; OPML import/export.

UI screenshots are not required in this document; later visual validation must cover
mobile, tablet, and desktop according to the standards of the project that
implements the application.

## 14. Phased delivery plan

### Phase 0 — Confirmation and project

- Confirm project name, repository, and designated branch.
- Confirm Miniflux as the preferred base reader; test the API, OPML import/export,
  read/unread, saved items, categories, search, attachments, and capture limits.
- Define initial general categories and select test sources from several topics;
  include the AI/models collection without making it the only topic.
- Agree on the initial usage channel (web only recommended) and the
  development/test environment.
- **Pre-product integration test:** integrate 5-10 real authorized feeds from
  different categories with Miniflux and validate that the user keeps access to all
  entries, order, available content, search, reading/favorites, and categories. Test
  reports with multi-category selection and a specific AI/models report. Evaluate
  Podcastfy with samples from different categories and technical Spanish. Use RSSHub
  only for official feeds not available natively. Run tests in the approved
  repository/branch; do not create a project copy.
- Review licenses, attribution notices, dependencies, security, privacy, Spanish
  quality, and operations. Exclude AI Summary Podcast's CC BY-NC code and Daily
  Digest's unclearly licensed code; keep them as references.
- Record reproducible evidence. By default reuse Miniflux + Podcastfy; replace one
  only if a test proves it fails a requirement.
- Review the available stack and the current Spanish TTS document.
- Create an approved issue with scope and criteria before modifying code.

**Output:** OSS compatibility matrix, integration evidence, product and dependency
license decision, authorized issue, and target repository. Do not start Phase 1
until this output is approved.

### Phase 1 — Skeleton and contracts

- Create the service structure and the bootstrap documentation required by the
  target repository.
- Integrate the chosen reader with approved authentication/configuration; define
  only extension contracts for reports, classification, and audio.
- Define sync/report/audio states and the complementary model the existing reader
  does not cover (do not duplicate entries, tags, or read-state).
- Create fixtures from verified sources and synthetic examples only for
  limits/failures; real entries come from authorized public sources.
- Validate contracts and the data model before enabling remote collection.

**Output:** the application starts, reproducible migrations, contracts, and
unit/contract tests.

### Phase 2 — Collector and feed

- Configure the integrated reader with 5-10 feeds from several areas; avoid
  rewriting its parser, scheduler, or reader unless the test identifies an
  essential gap.
- Implement own adapters only for important sources lacking a feed/API; add
  idempotency, visible errors, and URL controls.
- Add the curated package of example categories/sources and verify OPML, search,
  read state, and access to all entries.
- Run integrated tests respecting each source's policies and record which
  fields/content each feed does not deliver.

**Output:** every entry from integrated feeds can be queried and organized in the
reused reader; every entry keeps its original source.

### Phase 3 — Classification and entities

- Implement configurable general tags/categories and automatic suggestions that
  never hide or exclude entries from the reader.
- Create an evaluation set with entries from several areas and examples of ambiguous
  tags; add a subset of AI announcements, updates, papers, and analyses.
- Measure precision/recall per category and prefer "to be reviewed" when there is
  uncertainty; apply official-announcement-specific controls only to AI.

**Output:** general organization evaluated and, separately, AI enrichment evaluated;
original entries remain available even if the LLM fails.

### Phase 4 — Text report

- Period and filter selector; incremental cursor.
- Script based only on selected entries, with citations per claim.
- Citation validation, no-news handling, and report/history view.
- Tests for non-repetition, conflicts, dates, and attribution.

**Output:** auditable Spanish summary in text.

### Phase 5 — Audio

- Compare Spanish TTS with a common script: intelligibility of technical names,
  accents, numbers, acronyms, latency, cost, license/terms, and the possibility of
  local operation.
- Choose provider/voice after a documented test; do not include voice cloning in the
  MVP.
- Implement segmented generation, storage, player, and download.
- Test partial audio failure, regeneration, and text/audio correspondence.

**Output:** reproducible text and audio report, with a justified TTS decision.

### Phase 6 — Pilot and hardening

- Run a pilot with 8-15 feeds from several categories, including official AI/model
  feeds, for an agreed period.
- Review samples of ingestion coverage, organization, duplicates, reports, citations,
  and errors with the user.
- Validate SSRF security, limits, retention, accessibility, devices, and real costs.
- Fix approved issues; do not enable automatic delivery or public deployment without
  independent authorization.

**Output:** pilot evidence, explicit pending items, and a go/no-go recommendation.

## 15. Testing strategy and quality gates

- **Unit:** URL/date normalization, canonicalization, dedupe, category rules,
  cursors, TTS segmentation, schema validation, and permissions.
- **Contract:** each adapter transforms recorded/authorized real responses into the
  common schema; API endpoints keep the documented contract.
- **Integration:** persistence, scheduler, retries, idempotency, audio storage, and
  recovery of partial tasks.
- **E2E:** configure source -> import -> filter -> request report -> open citation ->
  play/download audio -> browse history.
- **Editorial quality:** a labeled set to detect official announcements, update vs.
  new model within AI; evaluate general category suggestions separately. Report
  evaluated by selected-entry coverage, factual precision, attribution, and
  repetition.
- **Security:** SSRF, redirects, DNS rebinding, malicious HTML, prompt injection from
  sources, large files, secrets, and access control.
- **Operations:** a failed source, API rate-limit, LLM/TTS unavailable, retry,
  cancellation, and recovery after a restart.
- Run lint, type checks, migrations, and existing suites before marking criteria as
  met. Tests with persistent services must use only the approved remote environment
  recorded in the target repository's `REMOTE.md`.

## 16. Pilot success metrics

Do not set invented values before the baseline. Record and agree thresholds after a
week of observation. Minimum metrics:

- percentage of successful source runs and freshness per source;
- percentage of received entries that remain available in the reader, without
  classification filtering;
- precision of general category suggestions and correction rate;
- for AI, official announcements detected and false positives against the reviewed
  set;
- percentage of factual statements with a valid source;
- rate of duplicate/repeated stories across reports;
- rate of reports and audio generated without failure;
- p50/p95 latency and cost per report in text and audio;
- human assessment of Spanish content, pronunciation, and usefulness;
- actual duration against the duration chosen by the user.

### Pilot acceptance conditions

- For each factual story in the report, the user can open a primary source, or it is
  explicitly stated that only secondary coverage exists.
- The system does not classify a third-party source as an official release without
  confirmation from the creator.
- "Since the last report" does not repeat stories already included without express
  action.
- A source failure does not block the rest of ingestion and remains visible.
- If audio fails, the text report remains available and audio can be retried without
  regenerating/repeating stories.
- The user understands the period, filters, time, and report version.

## 17. Decisions the owner must confirm before development

The agent receiving this plan must present these decisions in the startup issue or
document; do not invent operational values:

1. Product name and target repository/group.
2. Private individual use (recommended) or multi-user.
3. Initial interface: web only (recommended) or another channel.
4. Initial general categories, example feeds, and maximum acceptable frequency per
   source; AI/model feeds are a collection, not the only product content.
5. Default report duration/style and display timezone.
6. Remote, local, or both TTS; cost/privacy limits and Spanish voice.
7. Development environment and test server; persistent audio location.
8. Retention of entries, transcripts, and audio.
9. Whether use of a Feedly account/API is authorized; by default, do not depend on
   it.
10. Future automatic delivery policy; by default, explicit request only.

Initial recommendations, subject to approval: general-purpose reader, Miniflux as the
main reader and feed UI, Podcastfy for audio if it passes the tests, a complementary
application only for reports/audio, one user, on-demand reports in Spanish, example
feeds from several categories, an initial AI/models collection, five to eight
minutes as a flexible target, selectable TTS, and no voice cloning.

## 18. Instructions for the implementing agent

- This document is the initial specification, not permission to deploy, publish
  audio externally, create paid resources, or enable sources that require
  credentials.
- Before coding: verify the repository and `REMOTE.md`, review open and closed
  issues, look for duplicates, agree on the issue and its criteria, and confirm
  branch and environment. Respect the target repository's instructions, especially
  workspace and deployment limits.
- Implement in phases; do not create microservices in advance.
- Keep sources, prompts, models, voices, paths, and frequencies as typed
  configuration, not as scattered literals.
- Do not publish a story if it does not preserve its provenance; do not resolve
  uncertainty through an LLM-generated assertion.
- Keep the commit/push, image publication, deployment, and audio distribution phases
  separate; each requires the applicable authorization.
- Record metrics and pilot evidence before recommending production.

## 19. References consulted

- Feedly API: [introduction](https://developers.feedly.com/reference/introduction),
  [authorization and access requirements](https://developers.feedly.com/reference/authorization),
  [Ask AI API](https://developers.feedly.com/reference/ai-actions-experimental).
- Hugging Face Hub: [model API and webhooks](https://huggingface.co/docs/hub/en/api),
  [per-organization filters/listing](https://huggingface.co/docs/huggingface_hub/main/package_reference/hf_api).
- GitHub: [feeds REST API and Atom format](https://docs.github.com/en/rest/activity/feeds?apiVersion=2022-11-28).
- Project comparison:
  [AI Summary Podcast](https://github.com/applab-nl/ai-summary-podcast),
  [its CC BY-NC 4.0 license](https://github.com/applab-nl/ai-summary-podcast/blob/main/LICENSE),
  [Daily Digest](https://github.com/MarcelloMorettoni/daily-digest),
  [Podcastfy](https://github.com/souzatharsis/podcastfy),
  [Podcastfy's Apache-2.0 license](https://github.com/souzatharsis/podcastfy/blob/main/LICENSE),
  [Miniflux](https://github.com/miniflux/v2),
  [FreshRSS](https://github.com/FreshRSS/FreshRSS),
  [RSSHub](https://github.com/DIYgod/RSSHub).
- Licenses: [OSI Open Source Definition](https://opensource.org/osd),
  [Apache-2.0 license](https://www.apache.org/licenses/LICENSE-2.0.html).
- NotebookLM/Gemini Notebook: [generate an Audio Overview, consult sources, play and
  download](https://support.google.com/gemininotebook/answer/16212820?hl=en).
- OpenAI: [audio generation API](https://platform.openai.com/docs/api-reference/audio/json-object?lang=csharp).
- Example sources to verify during Phase 0: [OpenAI News](https://openai.com/news),
  [Anthropic News](https://www.anthropic.com/news),
  [Google DeepMind News](https://deepmind.google/blog/).
- Local TTS research referenced by the source material belongs to a separate
  repository and is not part of this project.

---

**Intended use:** hand this document to the agent that will design and build the
project. It must treat the Section 17 decisions as pending confirmation and must not
present the plan as an already implemented product.
