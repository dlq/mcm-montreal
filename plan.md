# Montreal MCM Roadmap

Date: 2026-04-26
Updated: 2026-05-11
Current release: `0.1.0`

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

Release `0.1.0` is live and includes:

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
- daily Cloudflare cron trigger

The local development app remains Flask + SQLite at `data/mcm.db`.

The production app runs the same Flask code in a Cloudflare Container and reads/writes D1 through an
authenticated Worker bridge. The production container must not depend on local disk for persistent
data.

## Production Facts

- GitHub repo: `dlq/mcm-montreal`
- Release tag `0.1.0`: Cloudflare container deployment baseline
- Cloudflare Worker: `montreal-mcm`
- Container application: `montreal-mcm-mcmcontainer`
- Live workers.dev URL: `https://montreal-mcm.dalaque.workers.dev`
- Custom domains configured in Wrangler: `montrealmcm.ca`, `www.montrealmcm.ca`
- D1 database: `montreal-mcm`
- D1 binding: `DB`
- D1 database id: `564167b2-abc1-4a66-8a26-0c95153eb72b`
- No R2 bucket is configured for this app.
- Worker secrets required: `MCM_SECRET_KEY`, `D1_BRIDGE_TOKEN`
- Cron trigger: `23 9 * * *`, which is 09:23 UTC daily. In Montreal/Toronto time that is 5:23 AM
  during daylight time and 4:23 AM during standard time.
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

Questions to settle:

- Is `montrealmcm.ca` resolving consistently, and should `www` redirect to apex or stay equivalent?
- Is the current Worker-to-container-to-D1 bridge fast enough for public browse traffic?
- Do we need a cheaper/faster read path for high-traffic pages, such as cached rendered pages or
  batched D1 bridge calls?
- What is the minimum monitoring needed before sharing the site more broadly?

Likely work:

- verify custom-domain DNS and TLS
- add a small deployment checklist to keep local, D1, and live health checks repeatable
- document recovery steps for a bad deploy
- add basic uptime checks or a scheduled health monitor
- make `/healthz` verify app process health without requiring D1
- add a separate deeper health endpoint or admin check that verifies D1 connectivity

### Refresh Reliability

The current cron calls the container refresh endpoint directly. It writes to D1, but source refresh
can take long enough that it is not safe to treat as a simple request/response cron forever.

Questions to settle:

- Should refresh run as one source per queue message, one source per scheduled request, or a
  Cloudflare Workflow?
- How much partial-refresh behavior is acceptable if one source fails?
- What status should the admin dashboard show while refresh is running?
- Should refresh failures alert the owner, or is admin-dashboard visibility enough for `0.1.x`?

Likely work:

- split refresh into per-source jobs
- make the cron enqueue or trigger source jobs and return quickly
- record refresh job status in D1
- expose last successful refresh per source in admin
- preserve existing conservative behavior: source failures should not deactivate existing inventory
  when a shop already has records

### Admin Safety

Admin routes are useful but should not remain casually reachable as production traffic grows.

Questions to settle:

- Use Cloudflare Access, a simple signed admin token, or another owner-only gate?
- Which admin routes should be public-impossible versus merely hidden?
- Should manual overrides require a lightweight audit trail?

Likely work:

- protect refresh and admin routes
- keep `/cron/*` and `/internal/*` unguessable and non-public
- keep manual notes, availability overrides, category overrides, and duplicate review durable in D1

### Data And Schema Hygiene

Questions to settle:

- Do we need a D1 backup/export routine before adding more write-heavy features?
- Should local SQLite migrations be formalized, or is D1 migration history enough for now?
- Which fields are genuinely source-derived versus admin-authored?

Likely work:

- add a repeatable D1 export/backup command
- keep migrations small and reviewable
- make seed/import paths explicit and avoid hand-editing derived data
- keep local `data/mcm.db` as development data, not a source of permanent facts

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

### 0.1.x Success Criteria

The `0.1.x` line is successful when:

- local development, deploy dry-run, Cloudflare deploy, and live health checks are routine
- the production app clearly reads/writes D1, not container disk
- refresh is reliable enough to trust daily
- admin paths are protected
- current source inventory feels dependable enough for repeated browsing

## 0.2.x Development: Retention And Better Discovery

The `0.2.x` line should make the product useful after the first visit. This is where saved searches,
alerts, history, and richer browsing should land.

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
