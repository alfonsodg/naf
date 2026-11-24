# Technical radar feed pack

Curated RSS/Atom pack for the `alfonso-articles` technical radar, delivered as a
single OPML document: [`alfonso-articles.opml`](alfonso-articles.opml). It carries
18 validated feeds, each with exactly one primary category from the approved
taxonomy and one radar subcategory, so importing it applies the organisation
instead of losing it.

- **Owner:** Alfonso de la Guarda.
- **Issue:** [`alfonsodg/naf` #33](https://github.com/alfonsodg/naf/issues/33),
  part of meta-issue #1 and of
  [`alfonso-articles` #1](https://scovil.labtau.com/ccvass/alfonso-articles/-/work_items/1).
- **Validated:** 2026-11-24, from the machine that authored the issue.

## Why OPML and not a URL list

The intake endpoint understands both formats, but only one of them preserves the
taxonomy:

- `parse_url_list` (`src/app/services/feed_documents.py`) reads one URL per line
  and leaves `categories` empty. Every feed would be added with no category.
- `parse_opml` walks the outline nesting and turns the trail into
  `candidate.categories`, which is the only path that assigns a category.
- `feed_intake` resolves `candidate.categories[0]` as the applied category
  (creating it when absent) and stores the rest as reported-only.

A plain text pack would therefore import successfully and silently lose the
whole categorisation. The pack is OPML for that reason, not as an export
convenience.

## Taxonomy

The top level is the approved taxonomy of `docs/PRODUCT_PLAN.md` §5 and decision
4: six general categories plus the separate AI/models collection.

1. `Technology and software`
2. `Science and research`
3. `Business and economics`
4. `Politics, regulation, and security`
5. `Health, education, culture, and media`
6. `User-defined custom categories`
7. `AI/models`

The second level is the radar subcategory from #33:

- `AI research`, `AI industry`, `AI open source`
- `General tech`, `Engineering`, `Hardware`, `Servers`, `Datacenter`
- `Security`, `Crypto`, `Crypto protocol`, `Crypto engineering`
- `Games`, `Wearables`, `Enterprise`

### First folder wins

The reader stores **one** category per feed. The intake applies the **first**
folder in the OPML trail and reports the remaining folders, which NAF keeps in
`feed_folders` and exposes through `GET /api/v1/feeds/folders`. The rule that
follows is binding for this pack:

- The **first** folder is always one of the seven top-level names above.
- The **second** folder is always the radar subcategory.
- The radar subcategory is therefore **reported-only**: it never becomes the
  reader category, and the report names the applied category separately from the
  reported folder.

Putting the radar heading first would create one reader category per radar heading
and leave the approved taxonomy unused, which breaks decision 4. The two-level
shape keeps the approved taxonomy applied and the radar visible in NAF's own
data.

### Mapping

| Radar subcategory | Applied top-level category | Feeds |
| --- | --- | --- |
| AI research | AI/models | arXiv cs.AI |
| AI industry | AI/models | SemiAnalysis |
| AI open source | AI/models | Hugging Face Blog |
| General tech | Technology and software | Hacker News, Lobsters, Techmeme |
| Engineering | Technology and software | IEEE Spectrum |
| Hardware | Technology and software | Phoronix |
| Servers | Technology and software | ServeTheHome |
| Datacenter | Technology and software | Data Center Dynamics |
| Crypto protocol | Technology and software | Ethereum Foundation Blog |
| Crypto engineering | Technology and software | Bitcoin Optech |
| Games | Technology and software | Game Developer |
| Wearables | Technology and software | DC Rainmaker |
| Enterprise | Technology and software | The Register |
| Security | Politics, regulation, and security | BleepingComputer, Krebs on Security |
| Crypto | Politics, regulation, and security | CoinDesk |

Crypto protocol and crypto engineering are engineering sources, so they sit with
technology and software; crypto market and regulation coverage sits with
politics, regulation, and security. The four top-level categories the pack does
not use yet — `Science and research`, `Business and economics`,
`Health, education, culture, and media`, and `User-defined custom categories` —
remain available for later feeds.

The mapping is data, not code. The owner can move any feed by editing the first
folder of its outline in the OPML and re-importing or patching the feed; no
application change is required.

## Editorial criteria

- Primary source (paper, official blog, regulator, vendor engineering blog) over
  secondary coverage.
- Technical substance over product announcements, funding, and rumours.
- One feed per source; no duplicate mirrors.
- A feed that only publishes excerpts is acceptable, but its content level must
  be stated.
- A source that blocks automated clients is paused, never silently dropped.
- The pack is a starting point; the owner can add or remove feeds without code
  changes.

## Pack and mapping

| Feed | Radar subcategory | Applied category | Site | Language | Cadence | Access |
| --- | --- | --- | --- | --- | --- | --- |
| arXiv cs.AI | AI research | AI/models | <https://arxiv.org> | English | Daily | Public, no auth; abstracts |
| SemiAnalysis | AI industry | AI/models | <https://semianalysis.com> | English | Irregular; last item 2025-09-16 | Public feed, no auth; site partly subscriber-only |
| Hugging Face Blog | AI open source | AI/models | <https://huggingface.co/blog> | English | Several per week | Public, no auth |
| Hacker News | General tech | Technology and software | <https://news.ycombinator.com> | English | Continuous | Public, no auth; link aggregator |
| Lobsters | General tech | Technology and software | <https://lobste.rs> | English | Several per day | Public, no auth; link aggregator |
| Techmeme | General tech | Technology and software | <https://www.techmeme.com> | English | Continuous | Public, no auth; aggregator excerpts |
| IEEE Spectrum | Engineering | Technology and software | <https://spectrum.ieee.org> | English | Several per week | Public, no auth |
| Phoronix | Hardware | Technology and software | <https://www.phoronix.com> | English | Several per day | Public, no auth |
| ServeTheHome | Servers | Technology and software | <https://www.servethehome.com> | English | About one per day | Public, no auth |
| Data Center Dynamics | Datacenter | Technology and software | <https://www.datacenterdynamics.com> | English | Several per day | Public, no auth |
| Ethereum Foundation Blog | Crypto protocol | Technology and software | <https://blog.ethereum.org> | English | Irregular; weekly to monthly | Public, no auth |
| Bitcoin Optech | Crypto engineering | Technology and software | <https://bitcoinops.org> | English | Weekly | Public, no auth |
| Game Developer | Games | Technology and software | <https://www.gamedeveloper.com> | English | About two per day | Public, no auth |
| DC Rainmaker | Wearables | Technology and software | <https://www.dcrainmaker.com> | English | Several per week | Public, no auth |
| The Register | Enterprise | Technology and software | <https://www.theregister.com> | English | Continuous | Public, no auth; Atom feed |
| BleepingComputer | Security | Politics, regulation, and security | <https://www.bleepingcomputer.com> | English | Several per day | Public, no auth |
| Krebs on Security | Security | Politics, regulation, and security | <https://krebsonsecurity.com> | English | Irregular; roughly weekly | Public, no auth |
| CoinDesk | Crypto | Politics, regulation, and security | <https://www.coindesk.com> | English | Continuous | Public, no auth |

Cadence is inferred from the publication dates of the ten most recent items in
the fetched document, not from a claimed schedule. Language is inferred from the
sources and their content; no non-English feed is included.

## Validation record (2026-11-24)

Method: one live request per feed from the authoring host with
`curl -m 12 -sSL -A 'naf-feed-validator/0.1'`, at most two attempts per feed,
body discarded after inspection. The status and content type are the ones the
server returned; the item date is the first `<pubDate>`, `<published>`, or
`<updated>` of the first `<item>` or `<entry>` in the document.

| Feed | Feed URL | HTTP | Content type | Last item | Verdict |
| --- | --- | --- | --- | --- | --- |
| arXiv cs.AI | `https://rss.arxiv.org/rss/cs.AI` | 200 | `application/rss+xml` | 2026-11-24 | Alive; added enabled |
| SemiAnalysis | `https://semianalysis.com/feed/` | 200 | `application/rss+xml; charset=UTF-8` | 2025-09-16 | Alive but stale; kept, owner may pause it |
| Hugging Face Blog | `https://huggingface.co/blog/feed.xml` | 200 | `application/rss+xml; charset=utf-8` | 2026-11-23 | Alive; added enabled |
| Hacker News | `https://news.ycombinator.com/rss` | 200 | `application/rss+xml; charset=utf-8` | 2026-11-24 | Alive; added enabled |
| Lobsters | `https://lobste.rs/rss` | 200 | `application/rss+xml` | 2026-11-24 | Alive; added enabled |
| Techmeme | `https://www.techmeme.com/feed.xml` | 200 | `text/xml` | 2026-11-24 | Alive; added enabled |
| IEEE Spectrum | `https://spectrum.ieee.org/feeds/feed.rss` | 200 | `application/rss+xml; charset=utf-8` | 2026-11-23 | Alive; added enabled |
| Phoronix | `https://www.phoronix.com/rss.php` | 200 | `text/xml; charset=utf-8` | 2026-11-24 | Alive; added enabled |
| ServeTheHome | `https://www.servethehome.com/feed/` | 200 | `application/rss+xml; charset=UTF-8` | 2026-11-23 | Alive; added enabled |
| Data Center Dynamics | `https://www.datacenterdynamics.com/en/rss/` | 200 | `application/rss+xml; charset=utf-8` | 2026-11-24 | Alive; added enabled |
| BleepingComputer | `https://www.bleepingcomputer.com/feed/` | 200 | `text/xml; charset=utf-8` | 2026-11-23 | Alive; added enabled |
| Krebs on Security | `https://krebsonsecurity.com/feed/` | 200 | `application/rss+xml; charset=UTF-8` | 2026-11-21 | Alive; added enabled |
| CoinDesk | `https://www.coindesk.com/arc/outboundfeeds/rss/` | 200 | `application/xml` | 2026-11-24 | Alive; added enabled |
| Ethereum Foundation Blog | `https://blog.ethereum.org/feed.xml` | 200 | `application/xml` | 2026-11-23 | Alive; added enabled |
| Bitcoin Optech | `https://bitcoinops.org/feed.xml` | 200 | `application/xml` | 2026-11-20 | Alive; added enabled; Atom |
| Game Developer | `https://www.gamedeveloper.com/rss.xml` | 200 | `text/xml; charset=utf-8` | 2026-11-23 | Alive; added enabled |
| DC Rainmaker | `https://www.dcrainmaker.com/feed` | 200 | `application/rss+xml; charset=UTF-8` | 2026-11-23 | Alive; first attempt timed out at 12 s, retry completed |
| The Register | `https://www.theregister.com/headlines.atom` | 200 | `application/xml` | 2026-11-24 | Alive; added enabled; Atom |

Notes on the two exceptions:

- **SemiAnalysis** answers with ten items, so the probe verdict is `alive`, but
  its last item is from 2025-09-16. It is kept because the owner named it in
  #33; the owner can pause it with `PATCH /api/v1/feeds/{id}` and resume it if
  the feed publishes again.
- **DC Rainmaker** is a large, slow feed: the first attempt received 245 KB and
  hit the 12 s limit. The second attempt completed in full (655 KB) with the
  status and date recorded above. Two attempts were made, then the result was
  accepted as observed.

Everything in the table was measured. No status, content type, or date is
inferred: where a value could not be captured, the record says so.

## Import

Set `NAF_BASE_URL` to the base URL of the running instance (the documented
development setup serves `http://localhost:8000`), then post the OPML:

```bash
curl -X POST "$NAF_BASE_URL/api/v1/feeds/intake" \
  -H 'Content-Type: application/xml' \
  --data-binary @feeds/alfonso-articles.opml
```

The response is one report row per candidate with its verdict, the category that
was applied, and the folders that were only reported. A feed is created only
when it answers with at least one item; a host that refuses automated clients is
added paused and marked unverified.

Every feed is declared `type="rss"`, the OPML 2.0 spelling for a syndication
feed, including the two Atom sources (Bitcoin Optech and The Register). The
intake reads `xmlUrl` and the outline trail; it does not depend on the declared
type.

### Idempotency

The pack can be posted again without duplicating subscriptions: every URL
already present in the reader comes back as a duplicate and nothing is created
twice. If the payload exceeds the batch limit, the remaining candidates are
reported as `not_processed`; resending the same document continues where the
call stopped, because the already-added feeds return as duplicates.

## Extending the pack

1. Validate the new feed first (HTTP 200, RSS or Atom, at least one recent item,
   no auth-only access).
2. Add an `<outline type="rss" ...>` inside an existing top-level category, with
   the radar heading as the second level.
3. Record the feed in the validation table above with its measured values.
4. Re-import; the report confirms the applied category and the reported folder.
5. Never add a new first-level name without a product decision: the seven
   top-level names are the approved taxonomy of decision 4.

Titles, site URLs, and folders are data in the OPML. Moving a feed between
categories, renaming a radar heading, or removing a feed never requires a code
change. For feeds already stored, `PATCH /api/v1/feeds/{id}` renames, moves to
another category, or pauses the subscription.

## Not in this pack

- **Classifier and report generator** (#5 and #6): separate issues.
- **Credentialed or paid-only sources**: out of scope. A public feed is the
  requirement; SemiAnalysis qualifies because its feed is public, even though
  parts of the site are subscriber-only.
- **Sites without a feed** (Chips and Cheese is the named example) and
  **security data sources that need an adapter** (CISA KEV, NVD, GitHub
  Advisory): separate adapter issues, not entries in this OPML.
- **Candidates still pending validation** from #33 (Digital Foundry, Wareable,
  Project Zero, Android Authority, 9to5Google, The Verge, GDC Vault, L2Beat,
  Ethereum Research, Bitcoin Optimum): not included, because no public feed was
  validated for them in this change. They are added by editing the OPML once
  their feed is validated.

## References

- `docs/PRODUCT_PLAN.md` §5 (initial taxonomy) and §17 decision 4 (six general
  categories plus the AI/models collection).
- `docs/STANDARDS.md` "Feed intake and validation" (verdicts, one feed one
  applied category, intake budget).
- `src/app/services/feed_documents.py` and `src/app/services/feed_intake.py`
  (the parsing and category rules this pack relies on).
