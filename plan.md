# Montreal MCM Roadmap

Date: 2026-04-26
Updated: 2026-05-15
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
- Release tag `0.1.2`: Cloudflare Queue-backed refresh baseline with Showroom and Le Centerpiece
  chunking
- Cloudflare Worker: `montreal-mcm`
- Container application: `montreal-mcm-mcmcontainer`
- Live workers.dev URL: `https://montreal-mcm.dalaque.workers.dev`
- Custom domains configured in Wrangler: `montrealmcm.ca`, `www.montrealmcm.ca`
- `www.montrealmcm.ca` redirects to `montrealmcm.ca` in the Worker.
- D1 database: `montreal-mcm`
- D1 binding: `DB`
- D1 database id: `564167b2-abc1-4a66-8a26-0c95153eb72b`
- No R2 bucket is configured for this app.
- Worker secrets required: `MCM_SECRET_KEY`, `D1_BRIDGE_TOKEN`, `MCM_ADMIN_TOKEN`,
  `MCM_MANUAL_REFRESH_TOKEN`
- Refresh cron trigger: `23 9 * * *`, which is 09:23 UTC daily. In Montreal/Toronto time that is
  5:23 AM during daylight time and 4:23 AM during standard time.
- Refresh monitor cron trigger: `23 11 * * *`, which is 11:23 UTC daily. In Montreal/Toronto time
  that is 7:23 AM during daylight time and 6:23 AM during standard time.
- Local `data/mcm.db` was refreshed and imported into D1 on 2026-05-10.
- D1 core-table counts after import: 6 shops, 850 listings, 116 crawl runs, 17 crawl failures, 25
  listing identity reviews.
- D1 listing count after the forced Le Centerpiece chunk refresh on 2026-05-12: 1,463 listings.
- Legacy local-account favourite tables (`users`, `favourite_listings`, `favourite_shops`) are not
  part of the production model. D1 migration `0002_drop_legacy_favourites.sql` drops them if present.

## Active Source Scope

Current active sources in code:

1. Morceau
2. Showroom Montreal
3. Montreal Moderne
4. Le Centerpiece
5. Maison Singulier
6. Yardsale Vintage
7. BOND Vintage
8. Chez Lamothe

Morceau should be treated as Vintage-collection-only ingestion. Its broader furniture and
new-arrivals collections include current-production design inventory outside the app scope.

Implementation stance:

- Maison Singulier uses Shopify live furniture collections and excludes archive collections.
- Yardsale Vintage uses Cargo's current Shop gallery and excludes the Archive gallery.
- BOND Vintage uses Shopify collection data, but the visible furniture inventory is currently sold
  out, so brand-new sold-out records are skipped by existing refresh semantics.
- Chez Lamothe uses the same Square Online storefront API as the public shop grid. This exposes
  prices, images, descriptions, detail URLs, and out-of-stock badges, so listings should not fall
  back to contact-for-details pricing unless the API omits a price.
- Chez Lamothe local refresh should stay materially faster than the earlier sitemap/product-page
  approach, but the hardcoded Square API path/cache version should be revisited if Square changes
  its published frontend API.
- Local pickup or local delivery is enough for Montreal and agglomeration-area shops right now;
  Canada-wide shipping is not required for local sources.
- If the product expands beyond the Montreal agglomeration, or traffic materially shifts toward
  users outside Montreal, revisit shipping requirements before adding more non-local sources.
- The next expansion direction should be regional road-trip sources: shops in Ottawa, Quebec City,
  Sherbrooke, the Eastern Townships, Lanaudiere, Laurentides, Outaouais, and route towns that either
  ship to Montreal or are practical 2-3 hour pickups from Montreal.

Deferred from the Montreal/agglomeration expansion:

1. EcoDepot Montreal, because the inventory is broad and may weaken focus unless carefully filtered.
2. Trianon Boutique, because it appears too weighted toward French antiques / 18th-century
   decorative arts for the current MCM-first product.
3. Vintage Home Boutique, because it remains useful Canada-friendly but is not on the immediate
   Ottawa / Quebec City / Townships regional pickup corridors.
4. Banana Lab, because the latest review suggests it should not be treated as Montreal-local.

Current source inventory may include some relevant lighting and decor from direct-shop pages. The
product scope should remain furniture-first until there is a deliberate decision to include selected
lighting and decor as first-class categories.

## 0.1.x Development: Stabilize The Live MVP

The `0.1.x` line made the live product dependable. It is closed at release `0.1.2`; remaining
reliability improvements now belong to `0.2.x` unless they are urgent production incidents.

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

Moved to `0.2.x`:

- add external uptime checks or alert delivery if log-only monitoring is not enough

### Refresh Reliability

The current cron enqueues refresh work through Cloudflare Queues. The queue consumer calls private
container refresh endpoints and writes to D1 through the Worker bridge. This became necessary
because Showroom Montreal and Le Centerpiece are too slow for a request-shaped per-source refresh.

Current decision:

- For `0.1.x`, refresh runs through Cloudflare Queues.
- Partial refresh success is acceptable: one source can fail without blocking the others.
- Production refresh messages run sequentially from the Worker queue consumer to avoid overloading
  the single Cloudflare container instance with multiple concurrent long crawls.
- Manual forced refreshes enqueue one source or all active sources and return quickly.
- D1 `refresh_jobs`, admin source status, and the second monitor cron provide current visibility.
- Cloudflare Workflows should be reconsidered only if refresh becomes multi-step orchestration with
  durable backoff, branching, or richer run history.

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

Completed in `0.1.2`:

- add a Cloudflare Queue binding and producer in `src/worker.js`
- add a queue consumer that runs refresh messages with controlled concurrency and retries
- keep a guarded manual refresh endpoint that enqueues one source or all active sources
- configure single-message queue batches, max concurrency 1, retries, and a dead-letter queue
- document queue creation, retry, dead-letter, and manual force-refresh behavior in
  `docs/operations.md`
- split Showroom Montreal into 12 queue chunks and filter its sold archive rows before ingestion
- split Le Centerpiece into 7 Shopify collection chunks and skip sold-out products in chunked
  refreshes
- keep chunk refreshes non-authoritative for now: chunks upsert current listings but do not
  deactivate missing inventory until a later source-wide reconciliation exists
- mark stale `running` refresh jobs from the monitor cron so admin status is not permanently noisy

Closure check:

- observe the next scheduled production refresh after queue chunking and confirm successful
  `refresh_jobs` rows for each active source/chunk

Moved to `0.2.x`:

- add owner alerting if admin-dashboard and log visibility are not enough
- add monitor cron status checks for suspicious hidden-count spikes

Forced production refresh notes from 2026-05-12:

- Morceau completed through the Worker-to-container-to-D1 path in about 10 seconds: 34 listings, 0
  new, 39 hidden.
- Montreal Moderne completed through the same path in about 15 seconds: 49 listings, 0 new, 37
  hidden.
- Showroom completed as 12 queue chunks after sold-archive filtering: 779 listings found, 504 new,
  no sold archive rows imported.
- Le Centerpiece completed as 7 queue chunks after the manual refresh token was rotated: 230 listings
  found, 18 new, all chunk jobs successful.

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

The `0.1.x` line is successful as of `0.1.2`:

- local development, deploy dry-run, Cloudflare deploy, and live health checks are routine
- the production app clearly reads/writes D1, not container disk
- refresh is reliable enough to trust daily
- admin paths are protected
- current source inventory feels dependable enough for repeated browsing

## 0.2.x Development: Retention And Better Discovery

The `0.2.x` line should make the product useful after the first visit. This is where saved searches,
alerts, history, richer browsing, and production-grade refresh orchestration should land.

### Queued Refresh And Monitoring

The `0.1.x` per-source cron model proved too request-shaped for Showroom and Le Centerpiece.
Cloudflare Queues are now the normal production refresh path as of `0.1.2`.

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

Completed in `0.1.2`:

- add a Cloudflare Queue binding and producer in `src/worker.js`
- add a queue consumer that runs one source refresh per message
- keep a guarded manual refresh endpoint that enqueues one source or all active sources
- configure single-message queue batches, max concurrency 1, retries, and a dead-letter queue
- document queue creation, retry, dead-letter, and manual force-refresh behavior in
  `docs/operations.md`
- split Showroom Montreal into 12 queue chunks and filter its sold archive rows before ingestion
- add a private Showroom chunk cron route in Flask for queue consumers
- keep Showroom chunk refreshes non-authoritative for now: chunks upsert current listings but do
  not deactivate missing Showroom inventory until a later source-wide reconciliation exists
- Showroom's Wix galleries include large sold archives; skip sold-out gallery items before ingestion
- deploy stale `running` job marking in the monitor cron so admin status is not noisy
- deploy Le Centerpiece collection chunks with sold-out Shopify products skipped in chunked refreshes
- confirm forced production runs for Showroom and Le Centerpiece complete as successful chunk jobs

Completed on 2026-05-14:

- forced the production queue-backed refresh path and observed all active source/chunk jobs complete
  successfully: Morceau 1/1, Montreal Moderne 1/1, Showroom Montreal 12/12, Le Centerpiece 7/7
- production health passed after the refresh, and D1 contained 1,464 listings

Likely `0.2.x` reliability work:

- add external uptime checks or alert delivery if log-only/admin-dashboard monitoring is not enough
- add monitor cron status checks for missing daily source jobs and suspicious hidden-count spikes
- investigate long-running source refreshes that write listings but leave `refresh_jobs` rows stuck
  as `running`; Chez Lamothe production ingestion populated D1 listings on 2026-05-15, but its
  job bookkeeping did not consistently reach `finish_refresh_job`
- review production secrets handling: confirm owner storage and rotation for `D1_BRIDGE_TOKEN`,
  decide whether `MCM_ADMIN_TOKEN` and `MCM_MANUAL_REFRESH_TOKEN` should remain shared or be split,
  and document the owner/rotation process
- consider a source-wide reconciliation job for chunked sources so missing inventory can be
  deactivated safely after all chunks succeed

Cloudflare resources created:

- `montreal-mcm-refresh`
- `montreal-mcm-refresh-dlq`

Decision:

- Cloudflare Queues are the current production refresh mechanism. Cloudflare Workflows should be
  reconsidered only if refresh becomes multi-step orchestration with durable backoff, branching, or
  richer run history.

### Saved Searches And Alerts

Questions to settle:

- Are anonymous saved searches enough, or do alerts require optional email capture?
- Should alerts be email-only, RSS-like feeds, or browser/session notifications first?
- What matching rules are useful without becoming noisy?

Likely work:

- saved search creation from current filters
- saved search management page
- alert preferences
- notification queue
- email when a saved search gets a new match
- email when a saved item changes status or appears removed

### Durable Anonymous Identity

Browser-session favourites are enough for the MVP, but they are fragile across devices.

Current decision:

- Avoid real user accounts for `0.2.x`.
- Prefer signed anonymous tokens for durable favourites, saved shops, and saved searches.
- Add optional email capture only if alerts need it; email should not imply a full account system.
- Revisit real accounts only if abuse prevention, cross-device sync, or alert preferences become
  unmanageable with anonymous tokens plus optional email.

Questions to settle:

- Should favourites, saved shops, and saved searches share one durable identity model?
- What personally identifiable data should be avoided until alerts require email?

Likely work:

- durable signed anonymous token model
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

Current decision:

- Maison Singulier, Yardsale Vintage, BOND Vintage, and Chez Lamothe have source definitions and
  local ingestion paths.
- Keep BOND Vintage active as a source, but expect zero public listings while its visible furniture
  inventory remains sold out.
- Treat Chez Lamothe as useful but slightly more coupled to Square Online internals than the
  Shopify/Cargo sources because it follows the public storefront API path observed in the browser.
- Revisit Green Wall Vintage now that regional road-trip sources are in scope; keep Vintage Home
  Boutique later because it is outside the Ottawa/Quebec City/Townships pickup corridors.
- Regional research on 2026-05-15 identified the next expansion set as Habitat Mobilier, Green Wall
  Vintage, and Mostly Danish.
- Deja Vu Meubles, Cornwall's Little Market, and A Fine Thing fit the regional taste/location
  criteria, but should wait because their public websites do not currently expose enough reliable
  item-level prices, details, and descriptions for ingestion on par with the existing shops.

Likely work:

- add Habitat Mobilier first if its public shop page can be parsed cleanly while excluding sold
  items from brand-new public ingestion
- add Green Wall Vintage next if its Shopify structure matches existing collection parsers
- spike Mostly Danish with strict category filtering because the site mixes vintage Scandinavian/MCM,
  outdoor teak, Oriental antiques, and services
- leave Deja Vu Meubles, Cornwall's Little Market, and A Fine Thing out of the next automated batch
  unless stable item feeds are verified
- monitor Chez Lamothe's Square storefront API path/cache version and add a fallback if it changes
- add profile/manual-source handling for high-quality local shops that still lack clean catalogs
- restore location on cards when inventory becomes meaningfully non-Montreal
- add source-specific notes for shipping and reliability; treat local delivery as enough inside the
  Montreal agglomeration, and revisit stronger shipping requirements when expansion or traffic moves
  beyond Montreal
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

- daily refresh for active sources
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
