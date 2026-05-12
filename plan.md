# Montreal MCM Roadmap

Date: 2026-04-26
Updated: 2026-05-12
Current line: `0.2.x`

## Purpose

This document is the durable roadmap for Montreal MCM: a focused discovery site for resale and
vintage mid-century modern furniture that is available in Montreal or can realistically be shipped
to Montreal.

The project started as a planning document. It now has a live MVP, so this file should stay
practical: current facts, release tracks, risks, and decisions that should survive chat context loss.

## Product Thesis

The site should not try to out-marketplace `1stDibs`, `Chairish`, or `Pamono`.

It should win by being:

- Montreal-specific
- direct-source-first
- cleaner and more focused than broad vintage marketplaces
- better at surfacing local Scandinavian, Danish, teak, and walnut inventory
- better at showing current availability from smaller local shops

The user promise is simple: browse a focused, live-looking catalogue of Montreal-relevant MCM
inventory without visiting each shop one by one.

## Current State

The live `0.1.x` MVP includes:

- listings feed with filtering and sorting
- listing detail pages
- shop index and shop detail pages
- browser-session favourite listings and shops
- freshness and availability labels
- bilingual English / French UI
- localized parsed price display, first-seen dates, and plural-aware listing counts
- admin tools for refreshes, failures, overrides, and duplicate review
- Cloudflare Worker + Container deployment
- Cloudflare D1 production database
- daily Cloudflare refresh cron and later refresh-monitor cron
- protected production admin routes

The local development app remains Flask + SQLite at `data/mcm.db`.

The production app runs the same Flask code in a Cloudflare Container and reads/writes D1 through an
authenticated Worker bridge. The production container must not depend on local disk for persistent
data.

## Production Facts

- GitHub repo: `dlq/mcm-montreal`
- Release tag `0.1.0`: Cloudflare container deployment baseline
- Release tag `0.2.0`: Cloudflare Queue-backed refresh baseline
- Cloudflare Worker: `montreal-mcm`
- Container application: `montreal-mcm-mcmcontainer`
- Live workers.dev URL: `https://montreal-mcm.dalaque.workers.dev`
- Custom domains configured in Wrangler: `montrealmcm.ca`, `www.montrealmcm.ca`
- `www.montrealmcm.ca` redirects to `montrealmcm.ca` in the Worker.
- D1 database: `montreal-mcm`
- D1 binding: `DB`
- D1 database id: `564167b2-abc1-4a66-8a26-0c95153eb72b`
- No R2 bucket is configured for this app.
- Worker secrets required: `MCM_SECRET_KEY`, `D1_BRIDGE_TOKEN`, `MCM_ADMIN_TOKEN`
- Refresh cron trigger: `23 9 * * *`, which is 09:23 UTC daily. In Montreal/Toronto time that is
  5:23 AM during daylight time and 4:23 AM during standard time.
- Refresh monitor cron trigger: `23 11 * * *`, which is 11:23 UTC daily. In Montreal/Toronto time
  that is 7:23 AM during daylight time and 6:23 AM during standard time.
- Local `data/mcm.db` was refreshed and imported into D1 on 2026-05-10.
- D1 core-table counts after import: 6 shops, 850 listings, 116 crawl runs, 17 crawl failures, 25
  listing identity reviews.
- Legacy local-account favourite tables (`users`, `favourite_listings`, `favourite_shops`) are not
  part of the production model. D1 migration `0002_drop_legacy_favourites.sql` drops them if present.

## Active Source Scope

Current active launch sources in code:

1. Morceau
2. Showroom Montreal
3. Montreal Moderne
4. Le Centerpiece

Morceau should be treated as Vintage-collection-only ingestion. Its broader furniture and
new-arrivals collections include current-production design inventory outside the app scope.

Deferred from the originally recommended first-wave source set:

1. Green Wall Vintage
2. Vintage Home Boutique
3. Maison Singulier

Green Wall Vintage and Vintage Home Boutique are not Montreal-local enough for the current early
build. Maison Singulier remains a later candidate.

Current source inventory may include some relevant lighting and decor from direct-shop pages. The
product scope should remain furniture-first until there is a deliberate decision to include selected
lighting and decor as first-class categories.

## 0.1.x Development: Stabilize The Live MVP

The `0.1.x` line should make the live product dependable. Prefer small, concrete fixes over broad
feature expansion.

### Deployment And Operations

Questions to monitor:

- Is `montrealmcm.ca` resolving consistently under external monitoring?
- Is the current Worker-to-container-to-D1 bridge fast enough for public browse traffic?
- Do we need a cheaper/faster read path for high-traffic pages, such as cached rendered pages or
  batched D1 bridge calls?
- What is the minimum monitoring needed before sharing the site more broadly?

Completed in `0.1.1`:

- make `/healthz` verify app process health without requiring D1
- add a separate deeper health endpoint or admin check that verifies D1 connectivity
- protect admin routes when `MCM_ADMIN_TOKEN` is configured
- redirect `www.montrealmcm.ca` to `montrealmcm.ca`
- add a repeatable operations runbook with deploy, health-check, backup, and bad-deploy recovery
  steps
- add `npm run d1:backup` and ignore local backup exports
- add `npm run prod:health` for repeatable public health, custom-domain, admin-auth, cron-blocking,
  D1 count, and refresh-job checks
- document production admin-token rotation so the owner can store the token outside the repository
- rotate `MCM_ADMIN_TOKEN` to an owner-stored value and verify authenticated `npm run prod:health`
- add a second daily cron that logs missing or non-success per-source refresh jobs

Remaining follow-up:

- add external uptime checks or alert delivery if log-only monitoring is not enough

### Refresh Reliability

The current cron triggers one private container refresh request per source. It writes to D1 and is
acceptable for the current launch-source set, but real production timing should decide whether this
needs Cloudflare Queues or Workflows later.

Current decision:

- For `0.1.x`, refresh runs as one private scheduled request per active launch source.
- Partial refresh success is acceptable: one source can fail without blocking the others.
- Production refresh source requests run sequentially from the Worker to avoid overloading the
  single Cloudflare container instance with multiple concurrent long crawls.
- Manual forced refreshes should call one source at a time because HTTP-triggered `waitUntil()` work
  is cancelled after a short post-response window.
- D1 `refresh_jobs`, admin source status, and the second monitor cron provide current visibility.
- Cloudflare Queues are planned for `0.2.x` if source count or refresh duration grows.

Completed in `0.1.1`:

- split refresh into per-source jobs
- make the cron trigger one private container refresh request per source instead of one long
  all-source request
- record refresh job status in D1
- expose last refresh job status per source in admin
- preserve existing conservative behavior: source failures should not deactivate existing inventory
  when a shop already has records
- fix Showroom's Wix `siteassets` URL decoding so BeautifulSoup's `&reg` entity handling does not
  corrupt `&registryLibrariesTopology` and trigger a non-ASCII URL failure in the container
- add a lightweight `/readyz` endpoint for Cloudflare container readiness checks separate from deep
  D1 health

Remaining follow-up:

- observe the next scheduled production refresh after the Showroom URL fix and confirm one
  successful `refresh_jobs` row per active source
- decide whether queue/workflow-backed refreshes are needed after real production timing data exists
- add owner alerting if admin-dashboard and log visibility are not enough

Forced production refresh on 2026-05-12:

- Morceau completed through the Worker-to-container-to-D1 path in about 10 seconds: 34 listings, 0
  new, 39 hidden.
- Montreal Moderne completed through the same path in about 15 seconds: 49 listings, 0 new, 37
  hidden.
- Showroom no longer hits the old non-ASCII URL failure, but the production request returns HTTP
  500 after roughly 94 seconds and leaves the `refresh_jobs` row running.
- Le Centerpiece returns HTTP 500 after roughly 106 seconds and also leaves the `refresh_jobs` row
  running.
- HTTP-triggered `waitUntil()` was cancelled after about 30 seconds, so manual all-source refreshes
  need one-source synchronous calls until queues/workflows exist.

### Admin Safety

Admin routes are useful but should not remain casually reachable as production traffic grows.

Current decision:

- For `0.1.x`, admin routes use a simple owner-controlled `MCM_ADMIN_TOKEN`.
- Worker-level public traffic blocks `/cron/*` and `/internal/*`.
- Cloudflare Access and explicit admin audit tables remain future options if operational risk grows.

Completed in `0.1.1`:

- protect admin routes, including manual admin refresh, when `MCM_ADMIN_TOKEN` is configured
- keep public Worker traffic from reaching `/cron/*` or `/internal/*`

Remaining follow-up:

- keep manual notes, availability overrides, category overrides, and duplicate review durable in D1
- decide whether manual overrides need an explicit audit table

### Data And Schema Hygiene

Questions to settle:

- Do we need a D1 backup/export routine before adding more write-heavy features?
- Should local SQLite migrations be formalized, or is D1 migration history enough for now?
- Which fields are genuinely source-derived versus admin-authored?

Completed in `0.1.1`:

- add a repeatable D1 export/backup command
- keep migrations small and reviewable
- make seed/import paths explicit and avoid hand-editing derived data
- keep local `data/mcm.db` as development data, not a source of permanent facts
- add D1 migration `0003_refresh_jobs.sql` for source-level refresh job tracking

Remaining follow-up:

- decide whether local SQLite migrations need a first-class migration runner beyond `ensure_schema`

### Source Parser Maintenance

Questions to settle:

- Should `mcm/sources.py` be split before adding more sources?
- Which parser failures deserve fallback data versus a visible source warning?
- Are direct-shop pages enough for the next few releases, or do some sources require Shopify/Wix
  helpers?

Likely work:

- split source definitions, fetch helpers, normalization helpers, and parser-specific code
- add source-level parser tests for current sources
- keep provenance and source URLs review-friendly
- clean legacy Showroom fallback and override URLs so seeded data follows the same source-page URL
  convention as live parsing

Decision after `0.1.1` review:

- keep the current source module for `0.1.x` because the live-dependability work is now covered and
  splitting parser files is a larger readability refactor with higher churn; revisit before adding
  more sources

### UX Polish

Questions to settle:

- Are listing cards dense enough for repeated browsing?
- Should cards show location only once non-Montreal sources are added?
- Should the public scope include lighting/decor now, or stay furniture-first?

Likely work:

- improve empty/filter states
- refine mobile filter ergonomics
- add a clear stale-data/freshness presentation where useful
- normalize listing-grid thumbnails enough that mixed source image canvases feel intentional

Decision after `0.1.1` review:

- keep UX polish out of the final `0.1.x` hardening pass unless a concrete browsing bug appears;
  move broader card-density, mobile-filter, and image-canvas refinements into `0.2.x` planning

### 0.1.x Success Criteria

The `0.1.x` line is successful when:

- local development, deploy dry-run, Cloudflare deploy, and live health checks are routine
- the production app clearly reads/writes D1, not container disk
- refresh is reliable enough to trust daily
- admin paths are protected
- current source inventory feels dependable enough for repeated browsing

## 0.2.x Development: Retention And Better Discovery

The `0.2.x` line should make the product useful after the first visit. This is where saved searches,
alerts, history, richer browsing, and production-grade refresh orchestration should land.

### Queued Refresh And Monitoring

The `0.1.x` per-source cron model proved too request-shaped for Showroom and Le Centerpiece. The
`0.2.0` implementation should make Cloudflare Queues the normal production refresh path.

Trigger conditions:

- source count reaches roughly 8-12 active shops
- total refresh duration regularly exceeds 2-3 minutes
- one flaky source regularly delays or obscures other source refreshes
- owner wants explicit alerts for missing, stuck, warning, or failing source refreshes

Preferred architecture:

- Cloudflare cron enqueues one refresh job per active source and returns quickly
- Cloudflare Queues process source jobs with controlled concurrency and retries
- Queue consumer calls the container's private per-source refresh endpoint or equivalent internal
  refresh function
- D1 `refresh_jobs` remains the durable status ledger for started, finished, success, warning,
  failure, listing counts, hidden counts, and error messages
- a later monitor cron checks D1 a couple of hours after the refresh window for missing, stuck, or
  repeated-failure jobs

Completed in `0.2.0`:

- add a Cloudflare Queue binding and producer in `src/worker.js`
- add a queue consumer that runs one source refresh per message
- keep a guarded manual refresh endpoint that enqueues one source or all active launch sources
- configure single-message queue batches, max concurrency 1, retries, and a dead-letter queue
- document queue creation, retry, dead-letter, and manual force-refresh behavior in
  `docs/operations.md`

In progress after `0.2.0`:

- split Showroom Montreal queued refreshes into staged category chunks
- add a private Showroom chunk cron route in Flask for queue consumers
- keep Showroom chunk refreshes non-authoritative for now: chunks upsert current listings but do
  not deactivate missing Showroom inventory until a later source-wide reconciliation exists
- after production tests on 2026-05-12, Showroom chunks 0-2 completed successfully with the sold
  archive filter in place
- Showroom's Wix galleries include large sold archives; skip sold-out gallery items before ingestion
  and keep chunk expansion tied to production verification

Remaining follow-up:

- deploy the full 12-chunk Showroom Worker with sold-archive filtering and confirm a forced
  Showroom run completes without importing sold archive rows
- mark stale `running` rows from older interrupted refresh attempts so admin status is not noisy
- decide whether Le Centerpiece also needs chunking, staged pagination, or a different parser path
- add monitor cron status checks for missing daily source jobs and suspicious hidden-count spikes
- decide whether stale `running` rows from interrupted jobs should be marked `stale` by the monitor

Cloudflare resources created:

- `montreal-mcm-refresh`
- `montreal-mcm-refresh-dlq`

Decision:

- Cloudflare Queues are the likely first step. Cloudflare Workflows should be reconsidered only if
  refresh becomes multi-step orchestration with durable backoff, branching, or richer run history.

### Saved Searches And Alerts

Questions to settle:

- Are anonymous saved searches enough, or do alerts force accounts/email identity?
- Should alerts be email-only, RSS-like feeds, or browser/session notifications first?
- What matching rules are useful without becoming noisy?

Likely work:

- saved search creation from current filters
- saved search management page
- alert preferences
- notification queue
- email when a saved search gets a new match
- email when a saved item changes status or appears removed

### Accounts Or Durable Anonymous Identity

Browser-session favourites are enough for the MVP, but they are fragile across devices.

Questions to settle:

- Is a full account system worth it, or should we use signed anonymous tokens first?
- Should favourites, saved shops, and saved searches share one durable identity model?
- What personally identifiable data should be avoided until alerts require email?

Likely work:

- durable favourite token or lightweight account model
- migration path from session favourites
- saved shops that survive browser session loss
- optional email capture only when needed for alerts

### Price And Availability History

Questions to settle:

- How much historical data should be kept for each listing?
- Should price history be public, admin-only, or used only for alerts and labels?
- How should removed/sold listings appear in public views?

Likely work:

- record price changes
- record availability changes
- show price drop or recently sold signals
- keep removed listings in internal history
- add listing timeline data for admin review

### Discovery Improvements

Questions to settle:

- Which filters are genuinely useful once inventory grows?
- Should search be simple text search, SQLite/D1 FTS, or an external search service later?
- Are designer/maker filters good enough without canonical entities?

Likely work:

- saved filters
- better text search
- designer/maker cleanup
- richer shop pages
- collection-style browse pages such as teak storage, lounge chairs, dining sets, lighting
- compare mode for multiple saved items

### Source Expansion

Questions to settle:

- Add Maison Singulier first, or wait until source parser organization is cleaner?
- Revisit Green Wall Vintage and Vintage Home Boutique only if scope expands beyond Montreal-local
  sources?
- When adding Ottawa, Toronto, Quebec City, or Canada-wide shops, how should card-level location and
  shipping badges return?

Likely work:

- add one carefully chosen second-wave direct source at a time
- restore location on cards when inventory becomes meaningfully non-Montreal
- add source-specific notes for shipping and reliability
- keep source additions conservative and review-friendly

### 0.2.x Success Criteria

The `0.2.x` line is successful when:

- users have a reason to come back
- saved searches and/or alerts work without creating trust issues
- favourites survive more than one browser session if the user chooses
- price and availability history improve confidence
- source expansion does not dilute the Montreal-first product feel

## 0.3.x Development: Authority, Content, And Scale

The `0.3.x` line should make the site feel like a durable destination rather than only a catalogue.
This is where editorial, SEO, normalized entities, broader source strategy, and monetization should
be considered.

### Editorial And SEO

Questions to settle:

- Which pages should be programmatic SEO versus hand-written editorial?
- What content is genuinely useful for Montreal buyers rather than generic MCM filler?
- Which category/shop/location pages deserve canonical indexable pages?

Likely work:

- editorial guides for Montreal MCM buying
- category landing pages
- shop profile improvements
- indexable designer/material/category pages once data quality supports them
- structured metadata
- sitemap and canonical URL policy

### Normalized Design Data

Questions to settle:

- When do `designer` and `maker` need to become canonical entities?
- Should aliases and source evidence be admin-reviewed?
- Is this necessary for search quality, SEO, alerts, or all three?

Likely work:

- `creators` or `design_entities` model
- aliases and canonical display names
- source evidence and confidence
- admin review for ambiguous designer/maker extraction
- entity pages only after quality is high enough

### Broader Marketplace Strategy

Questions to settle:

- Should the product stay direct-source-first indefinitely?
- Would marketplace ingestion create too much noise, staleness, or duplicate handling work?
- Which sources are worth monitoring manually before automating?

Likely work:

- explicit Facebook Marketplace recheck for current and candidate sources
- direct-vs-marketplace source badges if marketplace data is added
- stricter duplicate handling across source types
- rules for excluding low-quality or irrelevant decor

### Trade And Monetization

Questions to settle:

- Is the site primarily a buyer utility, an SEO property, or a trade workflow tool?
- Would designers value boards, private notes, alerts, or exportable shortlists?
- Are affiliate links or paid shop placements compatible with trust?

Likely work:

- trade-oriented saved boards
- private notes on saved items
- shareable shortlists
- analytics for outbound source clicks
- careful monetization experiments only after the core catalogue is trusted

### 0.3.x Success Criteria

The `0.3.x` line is successful when:

- the site has credible indexed discovery pages
- richer content improves buyer confidence rather than distracting from inventory
- normalized entities improve search and browsing quality
- any broader source or monetization strategy preserves trust

## Cross-Cutting Risks

### Source Fragility

Source markup will drift. Keep ingestion conservative, source-specific, and easy to review.

Mitigation:

- small source set first
- parser tests for important sources
- source-specific notes
- fallback data only as a bootstrap or failure cushion, not as a substitute for live data

### Inventory Staleness

The product loses trust quickly if sold or removed items look current.

Mitigation:

- daily refresh for launch sources
- source-level freshness labels
- conservative deactivation rules
- clear admin visibility into refresh failures

### Mixed Inventory

Some sources mix furniture, lighting, decor, and current-production pieces.

Mitigation:

- furniture-first public scope
- explicit source collection choices
- review categories before broadening scope

### Duplicate Items

The same item can appear under changed source URLs or across marketplaces.

Mitigation:

- stable source keys where possible
- reconciliation by title, image, price, and description
- admin duplicate review queue
- keep provenance visible

### D1 Bridge Performance

The current production bridge preserves the Flask app but adds HTTP calls between the container and
Worker D1 binding.

Mitigation:

- measure public page timings
- batch bridge calls where practical
- cache read-heavy public responses if needed
- keep the option open to move selected read paths into Worker-native code later

## Bottom Line

For `0.1.x`, make the live Cloudflare MVP boring and dependable.

For `0.2.x`, add retention: saved searches, alerts, durable favourites, history, and careful source
growth.

For `0.3.x`, build authority: editorial discovery, normalized entities, broader source strategy, and
trade workflows only where they reinforce trust.
