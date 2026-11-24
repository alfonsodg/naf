# Pilot results

| | |
|---|---|
| **Project** | naf — Categorized feed aggregator with audio reports |
| **Date** | 2026-11-24 |
| **Environment** | Sandbox `sandbox-ud-ord`, compose project `naf` |
| **Image** | `ghcr.io/alfonsodg/naf:feat-5-1` |
| **Cohort** | 18 feeds imported from `feeds/alfonso-articles.opml` |
| **Window** | seven days, read from `GET /api/v1/metrics?days=7` |

## Reading

Snapshot taken on 2026-11-24 after the first end-to-end run:

| Block | Value |
| --- | --- |
| Sources | 18 feeds, reader available, 0 parsing errors |
| Ingestion | 3 runs, 3 successes, 0 failures, success rate 1.0 |
| Entries captured | 1,255 across the runs, 418 per run on average |
| Reports | 7 editions: 2 ready, 1 no-news, 3 failed, 1 no-news after the fix |
| Report selection | 8 to 20 entries per edition |
| Audio | 2 assets, 1,002.7 s of speech, 48.1 MB |
| Freshness | 15 of 18 feeds outside twice the polling interval at the moment of the snapshot |

The three failed editions came from the output truncation that the current
defaults (40 entries, 120 s, 6,000 tokens) fix; the editions generated after the
change are `ready`.

## Evidence

- Report 7: 8 entries, 6 stories, every claim cited, `prompt_version` 1.1,
  `official=false` on the third-party stories.
- Report 6 audio: 502.4 s, 37 timed segments, served as `audio/wav` and played
  in the interface with the transcript synced.
- Entry 2579 classification: category `Inteligencia Artificial`, five tags,
  `source=auto`, no review needed.
- The reader was recreated with explicit retention: 90 days for read entries,
  180 for unread, cleanup daily.

## Security and exposure

- The API has no authentication of its own; the only public surface is the
  nginx proxy with HTTP Basic auth, and `/health` stays open for probes.
- The API keeps its loopback binding; the databases are not published.
- SSRF protections (resolution plus pinning, IPv4 preference) are covered by
  unit tests and exercised by the intake of 18 public feeds.
- Dependency audit is clean without ignores.

## Accessibility and devices

Not validated in a real browser: Playwright is not available in the authoring
environment. The pages use semantic landmarks, labelled controls, a skip link,
and responsive CSS; visual and assistive-technology checks remain open.

## Recommendation

Conditional go for the text-and-audio flow: ingestion is reliable over the
window, reports and audio are produced and cited, and the exposure boundary
holds. Before an unconditional go:

1. a human review of Spanish quality and pronunciation on two editions;
2. a browser pass at 360 px, tablet, and desktop;
3. the retention window reviewed after a full cleanup cycle.
