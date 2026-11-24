# Pilot Plan: 12 feeds, seven days, and a go/no-go

| | |
|---|---|
| **Project** | naf — Categorized feed aggregator with audio reports |
| **Version** | Unreleased |
| **Created** | 2026-11-24 |
| **Updated** | 2026-11-24 |
| **Author** | Alfonso de la Guarda Reyes |
| **Location** | `docs/PILOT_PLAN.md` |

Plan for Phase 6 of [`#8`](https://github.com/alfonsodg/naf/issues/8), under
meta-issue [`#1`](https://github.com/alfonsodg/naf/issues/1). It defines the
cohort, the observation window, the readings, the security and accessibility
checks, and the evidence the pilot must attach. It records no result: the
readings, findings, and recommendation belong to `docs/PILOT_RESULTS.md` and to
the issues filed from them.

The measurable half is served by `GET /api/v1/metrics?days=7`. Every number in
that response comes from NAF-owned rows plus `reader.list_feeds()`; the pilot
never copies a number by hand from a different source.

## 1. Preconditions

- The phases declared as blockers in `#8` are closed, or the owner has waived
  one explicitly in that issue. A pilot started over an unfinished phase
  measures an incomplete product, not the plan.
- The stack runs on the Sandbox host named in `INFRA.md`, with PostgreSQL,
  Miniflux, the NAF API, an OpenAI-compatible LLM, and the Spanish TTS voice
  configured. The API is not published on a public interface.
- The imported pack is `feeds/alfonso-articles.opml`, imported through
  `POST /api/v1/feeds/intake`. `feeds/README.md` records the mapping and the
  validation of every feed.
- The baseline is taken only after the first successful collection pass: a
  window that starts before the reader has polled the cohort measures an empty
  database.

## 2. Pilot cohort

The pack carries 18 feeds. The pilot imports it as delivered and then pauses the
six feeds outside the cohort with
`PATCH /api/v1/feeds/{id}` and `{"disabled": true}`. Pausing keeps their entries
and read state; deleting would cascade the reader deletion over every entry.
The snapshot then reports `sources.feeds: 18`, `sources.disabled: 6`, and the
freshness of the 12 active feeds, which is the pilot cohort.

| Feed | Applied category | Feed URL |
| --- | --- | --- |
| arXiv cs.AI | AI/models | <https://rss.arxiv.org/rss/cs.AI> |
| Hugging Face Blog | AI/models | <https://huggingface.co/blog/feed.xml> |
| SemiAnalysis | AI/models | <https://semianalysis.com/feed/> |
| Hacker News | Technology and software | <https://news.ycombinator.com/rss> |
| Lobsters | Technology and software | <https://lobste.rs/rss> |
| IEEE Spectrum | Technology and software | <https://spectrum.ieee.org/feeds/feed.rss> |
| Phoronix | Technology and software | <https://www.phoronix.com/rss.php> |
| The Register | Technology and software | <https://www.theregister.com/headlines.atom> |
| Bitcoin Optech | Technology and software | <https://bitcoinops.org/feed.xml> |
| BleepingComputer | Politics, regulation, and security | <https://www.bleepingcomputer.com/feed/> |
| Krebs on Security | Politics, regulation, and security | <https://krebsonsecurity.com/feed/> |
| CoinDesk | Politics, regulation, and security | <https://www.coindesk.com/arc/outboundfeeds/rss/> |

Paused for the window: Techmeme (aggregator with overlapping excerpts),
ServeTheHome, Data Center Dynamics, Ethereum Foundation Blog, Game Developer,
and DC Rainmaker. They remain available after the pilot; no feed is dropped.

SemiAnalysis last published on 2025-09-16. It stays active because the owner
named it in `#33`; the source block will show it as stale until it publishes
again, and that reading is the point. If it stays silent for the whole window,
the owner may pause it after the pilot and record the decision.

## 3. Observation window

- **Duration:** seven consecutive days, read as `?days=7`. The window ends at
  the `generated_at` instant of each snapshot.
- **Baseline:** immediately after the first successful pass over the cohort.
- **Closing reading:** after the seventh day, before pausing or changing any
  feed.
- **Collection cadence:** one `POST /api/v1/collect` pass at 09:00 UTC and one
  at 21:00 UTC each day; the response names its `ingestion_run_id`. The reader
  keeps polling every 20 minutes, which is the interval the freshness check
  uses.
- **Cohort stability:** no feed is added, removed, or resubscribed during the
  window. A source that dies stays in place and is recorded as a failure; a
  feed is paused only if the owner decides it, and the decision is written in
  the results.
- **Reading:** save the raw JSON of both snapshots and attach them to `#8` with
  the command that produced them.

```bash
curl -sS "$NAF_BASE_URL/api/v1/metrics?days=7" | jq . > metrics-day0.json
# ... seven days later ...
curl -sS "$NAF_BASE_URL/api/v1/metrics?days=7" | jq . > metrics-day7.json
```

`window_start` and `generated_at` are copied into `docs/PILOT_RESULTS.md` so a
reader knows which seven days the numbers describe.

## 4. Metrics and targets

The plan fixes no success threshold before the baseline; `PRODUCT_PLAN.md` §16
requires recording and agreeing thresholds after a week. The `Target` column
therefore separates the conditions that are binary in the plan from the rates
whose threshold is agreed at day 7.

| Metric | Reading | Target |
| --- | --- | --- |
| Source freshness | `sources.checked_in_window`, `sources.stale`, `sources.newest_checked_at`, `sources.oldest_checked_at` | Every active feed checked within twice the polling interval; a stale feed names the interval it missed |
| Parsing failures | `sources.parsing_errors` | Baseline first; a new parsing error is visible in the snapshot and in `GET /api/v1/feeds/health` |
| Source success rate | `ingestion.success_rate`; per-feed detail from the `errors` of each run in `GET /api/v1/ingestion-runs` | Baseline first; threshold agreed at day 7 |
| Pass size | `ingestion.entries`, `ingestion.average_entries` | Baseline first; no pass may truncate a feed silently |
| Report success | `reports.editions`, `reports.ready`, `reports.no_news`, `reports.failed` | Every failure is stored and explainable; no silent loss |
| Report size | `reports.average_included_entries` | Baseline first; the selection never exceeds `NAF_REPORT_MAX_ENTRIES` |
| Text wall time | `reports.p50_seconds`, `reports.p95_seconds` | Baseline first; threshold agreed at day 7 |
| Audio coverage | `audio.assets`, `audio.duration_seconds`, `audio.size_bytes`, `audio.editions_with_audio` | Every ready edition can be voiced on request; audio failure leaves the text available |
| Entries available | `GET /api/v1/entries` count against the collected count in the run history | No classification filtering removes a received entry from the reader |
| Citation validity | Manual review of every story in the sampled reports | 100 % of factual stories open a primary source, or say that only secondary coverage exists |
| Duplicate stories | Manual review of the five scenarios, especially `since_last` | "Since the last report" repeats nothing without an explicit request |
| AI classification | Manual review of the AI stories against the creator's announcement | No third-party item is presented as an official launch |
| Spanish quality | Listening and reading the sampled reports | Human assessment recorded; pronunciation and usefulness accepted by the owner |
| Duration vs target | Stored audio duration against the chosen 5–8 minute target | Difference recorded per edition; no invented tolerance |
| Cost per report | Provider billing for text; measured synthesis time for local audio | Recorded per edition, text and audio separately |
| Accessibility and devices | Section 6 | No blocker on the three viewports and the keyboard path |

Fields absent from `GET /api/v1/metrics` are read from the route named beside
them or from the manual review; they are never estimated. The endpoint keeps
returning zeros and `null` when there is nothing to measure, and marks only the
source block unavailable when the reader fails.

## 5. Scenarios

Run each scenario on the cohort and attach the edition identifier, the citation
check, and the audio result.

| Scenario | Request | What must hold |
| --- | --- | --- |
| Full period | `POST /api/v1/reports` with the seven-day period | Every story cites a source; the edition stores its filters and period |
| Category filter | Same period, `category_ids` for AI/models and for Technology and software | Only entries from those categories appear; the filter is visible in the edition |
| Since last | `since_last: true` immediately after a report | No story repeats the previous edition unless the owner asks for it |
| Multi-category | Period plus two categories and a tag | The selection is the intersection the reader applies; the UI states it |
| AI-specific | AI/models only, reviewed against the creator's post | `new_model`, `model_update`, `release`, and `analysis` are not conflated |

For each scenario, open every citation from the report page, play the audio if
it was generated, and verify the transcript follows the spoken segment. A failed
audio run must leave the text edition readable and retryable with
`POST /api/v1/reports/{id}/audio`.

## 6. Security checklist

The checklist is executed during the pilot, not assumed from the architecture.
Each item is marked with its evidence; a failed item becomes an issue in the
same turn it is found.

### SSRF and outbound requests

- [ ] Only `http` and `https` pass `validate_feed_url`; credentials in the URL
      are rejected and literal private, loopback, link-local, reserved, and
      metadata addresses are refused.
- [ ] A public name that resolves to a private address is refused by the
      resolver, and the connection is pinned to the validated address.
- [ ] Every redirect hop is re-validated before it is followed; a redirect into
      a private target aborts the probe.
- [ ] There is no host allowlist in the MVP. The check is scheme plus resolved
      address, which is wider than an allowlist; record that decision and its
      tests in the results.
- [ ] Probe timeout, response size cap, and concurrency limits are the
      configured values, not defaults inherited from a library.

### Exposure and access

- [ ] The API listens on loopback or the Sandbox network only; `GET /health`
      and `GET /api/v1/metrics` are not reachable from a public interface.
- [ ] Miniflux is reachable only through the internal URL; the browser never
      receives the reader token.
- [ ] If a reverse proxy is used, its basic-auth boundary is verified and
      recorded (see `#47`); the MVP has no authentication layer of its own.

### Secrets and content

- [ ] `.env*` files, the Miniflux token, the LLM key, and SSH material are
      absent from Git and from API responses; `git grep` finds no secret.
- [ ] Logs and stored errors redact the provider key; a failed report keeps a
      readable reason without the credential.
- [ ] Feed content is treated as data: no HTML or script is executed, no tool
      is invoked from an entry, and the model cannot invent a citation because
      URLs come from the stored entry.
- [ ] Prompt-injection probes are tried in a feed title and body; the report
      either refuses the instruction or keeps it as quoted content, and the
      citation validation still holds.

### Dependencies and build

- [ ] `uv audit --no-extra audio` and `bandit -r src/ -q` pass or their
      advisories are triaged in issues before the closing snapshot.
- [ ] The runtime image is scanned with the available scanner on the Sandbox
      (`trivy image` when installed); the result is attached even when clean.
- [ ] No optional audio extra is installed in the runtime image; the TTS and
      LLM packages used by the pilot are the documented ones.

## 7. Accessibility and devices

- [ ] Report page at 360×640, 768×1024, and 1440×900: no horizontal overflow,
      readable body text, controls reachable without zoom.
- [ ] Keyboard-only path: create a report, open a citation, play and pause the
      audio, seek by transcript segment, and retry a failed audio run.
- [ ] Focus is visible, the player has an accessible name, and the transcript
      segment being spoken is not conveyed by colour alone.
- [ ] Spanish labels, periods, filters, and version are visible on the page;
      no mixed English string reaches the user.
- [ ] Screenshots and the Playwright session record are attached to `#8`; the
      run happens on the Sandbox host, not on the owner's workstation.

## 8. Evidence attached to `#8`

- The baseline and closing `GET /api/v1/metrics?days=7` JSON, with the command
  and the `generated_at` instant of each.
- The run history export and the per-feed errors of every failed pass.
- One edition per scenario, with its citations, audio asset, and duration.
- The security checklist with the command that produced each result, including
  a clean dependency and image scan.
- The accessibility screenshots and the keyboard-path record.
- Every finding filed as an issue, with its evidence and the fix status.

## 9. Go/no-go

The recommendation is `go` only when every binary acceptance condition in
`PRODUCT_PLAN.md` §16 holds, the metrics baseline is recorded with agreed
thresholds, and no open issue blocks a condition. A failed condition produces a
`no-go`, a remediation issue, and a repeat of the affected scenario; it is not
waived in prose.

The decision is written in `docs/PILOT_RESULTS.md` with the rationale, the
closing snapshot, and the list of pending items. No production deployment is
part of this plan: the pilot validates the product on the Sandbox, and any
promotion keeps its own approval.
