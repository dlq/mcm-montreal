# Montreal MCM Roadmap

Date: 2026-04-26
Updated: 2026-05-29
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

The app should stay web-first but become a complete installable web app on iOS and Android:
installable/pinnable, fast to reopen, visually coherent in standalone mode, notification-capable
where users explicitly opt in, and useful without requiring a native app.

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
- lazy-loaded listing cards in 48-card batches on the public browse page
- durable anonymous favourites, saved shops, and saved searches
- bilingual synonym-expanded listing search with weighted default ranking
- listing detail history for recorded price and availability changes

The local development app remains Flask + SQLite at `data/mcm.db`.

The production app runs the same Flask code in a Cloudflare Container and reads/writes D1 through an
authenticated Worker bridge. The production container must not depend on local disk for persistent
data.

## Production Facts

- GitHub repo: `dlq/mcm-montreal`
- Release tag `0.1.0`: Cloudflare container deployment baseline
- Release tag `0.1.2`: Cloudflare Queue-backed refresh baseline with Showroom and Le Centerpiece
  chunking
- Release tag `0.2.1`: regional source expansion baseline with Habitat Mobilier, Green Wall
  Vintage, and gradual Mostly Danish ingestion
- Release tag `0.2.2`: public browse performance release with 48-card lazy loading and a rotated
  Cloudflare container instance so the deployed container serves the current image
- Release tag `0.2.3`: shop address and compact map release with production D1 address metadata
  populated
- Release tag `0.2.4`: cleanup release for designer/maker filter normalization, guarded chunked
  source reconciliation, refresh audit tooling, production secret documentation, and Habitat
  Squarespace gallery image selection
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
- Production source expansion checks on 2026-05-18 confirmed public listings for Habitat Mobilier
  (21), Green Wall Vintage (19), and the first gradual Mostly Danish chunk slice.
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
7. Chez Lamothe
8. Habitat Mobilier
9. Green Wall Vintage
10. Mostly Danish

Morceau should be treated as Vintage-collection-only ingestion. Its broader furniture and
new-arrivals collections include current-production design inventory outside the app scope.

Implementation stance:

- Maison Singulier uses Shopify live furniture collections and excludes archive collections.
- Yardsale Vintage uses Cargo's current Shop gallery and excludes the Archive gallery.
- Chez Lamothe uses the same Square Online storefront API as the public shop grid. This exposes
  prices, images, descriptions, detail URLs, and out-of-stock badges, so listings should not fall
  back to contact-for-details pricing unless the API omits a price.
- Chez Lamothe local refresh should stay materially faster than the earlier sitemap/product-page
  approach, but the hardcoded Square API path/cache version should be revisited if Square changes
  its published frontend API.
- Habitat Mobilier uses Squarespace store JSON. Treat only in-stock product rows as current public
  inventory so sold archive rows do not create brand-new public records.
- Green Wall Vintage uses Shopify collection JSON with non-furniture products filtered out.
- Mostly Danish uses selected Shopify furniture collections only; outdoor, Oriental, accents, and
  archive collections stay excluded because the broader site mixes several non-MCM categories.
- Mostly Danish may still include a meaningful amount of later modern furniture that feels outside
  the MCM focus. Avoid subjective item-by-item filtering for now, but revisit its collection scope,
  shop weighting, or source notes if it starts diluting the catalogue.
- Mostly Danish is intentionally ingested gradually: production refreshes enqueue 5 of 30 bounded
  Shopify collection-page chunks per run so the large catalogue does not monopolize the queue.
- The default browse feed should not let Mostly Danish dominate new items while its initial bulk
  ingest is recent. Keep explicit newest sorting available, but use curated default ordering to
  surface other sources first.
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

## Roadmap History

Closed release-track planning, including the completed `0.1.x` stabilization plan, lives in
`docs/roadmap-history.md`. Keep this file focused on current state, active release planning, future
tracks, and cross-cutting risks.

## 0.2.x Development: Retention And Better Discovery

The `0.2.x` line should make the product useful after the first visit. This is where saved searches,
history, richer browsing, and production-grade refresh orchestration should land. Saved-search push
alerts are deferred into the broader installable web-app/PWA effort, because notification behavior
is device-specific and most useful once the site can be pinned on iOS and Android.

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
- rotate the named Cloudflare container instance when a deployed image needs a fresh warm container
  to pick up the current filesystem

Completed on 2026-05-14:

- forced the production queue-backed refresh path and observed all active source/chunk jobs complete
  successfully: Morceau 1/1, Montreal Moderne 1/1, Showroom Montreal 12/12, Le Centerpiece 7/7
- production health passed after the refresh, and D1 contained 1,464 listings

Likely `0.2.x` reliability work:

- add external uptime checks or alert delivery if log-only/admin-dashboard monitoring is not enough

Cloudflare resources created:

- `montreal-mcm-refresh`
- `montreal-mcm-refresh-dlq`

Completed in `0.2.x`:

- harden the refresh monitor so it checks all same-day refresh rows rather than only the latest row
  per source
- validate expected same-day job counts for chunked sources: Showroom Montreal, Le Centerpiece, and
  Chez Lamothe
- log monitor warnings for missing jobs, non-success jobs, still-running jobs, suspicious
  hidden-count spikes, and unknown source slugs
- add chunk metadata to `refresh_jobs` so chunked source failures can identify the affected
  `chunk_index` and source URL instead of only reporting source-level counts
- add `npm run prod:refresh-audit` for repeatable production refresh-job audits
- audit production `refresh_jobs` on 2026-05-29: no currently running jobs, all daily runs from
  2026-05-22 through 2026-05-29 reached the expected 51 successful jobs, and recent warnings were
  transient Showroom Montreal DNS failures or one Montreal Moderne `IncompleteRead`
- document production secret purposes, owner storage expectations, and rotation checks; keep
  `MCM_ADMIN_TOKEN` and `MCM_MANUAL_REFRESH_TOKEN` separate so admin credentials cannot force
  manual refreshes
- add guarded source-wide reconciliation for fully refreshed chunked sources: Showroom Montreal,
  Le Centerpiece, and Chez Lamothe now enqueue a reconciliation message after their chunks, and the
  Flask reconcile endpoint hides missing inventory only when every expected chunk has a successful
  job newer than the queue batch timestamp

Decision:

- Cloudflare Queues are the current production refresh mechanism. Cloudflare Workflows should be
  reconsidered only if refresh becomes multi-step orchestration with durable backoff, branching, or
  richer run history.

### Saved Searches And Alerts

Questions to settle:

- Are anonymous saved searches enough for non-alert retention?
- Should post-PWA alerts use Web Push first, with optional email left out until there is a clear need?
- What matching rules are useful without becoming noisy?

Likely work:

- saved search creation from current filters
- saved search management page
- defer alert preferences, notification queue, Web Push subscriptions, and any email capture until
  the broader installable web-app/PWA work begins

Completed in `0.2.x`:

- saved searches share the durable anonymous identity model with favourites
- users can save the current listing filters and manage saved searches from the existing Favourites
  page
- saving a search after HTMX filter updates now captures the current visible filter form, with a
  same-origin referrer fallback for empty posts
- the Favourites nav count reflects saved listings, saved shops, and saved searches together
- saved search alerts and email capture remain deferred until the broader installable web-app/PWA
  work; the likely first alert path is anonymous Web Push tied to the existing durable owner key,
  with in-app saved search state as the reliable fallback

### Audience Analytics

Current facts:

- Cloudflare zone analytics can report daily unique IPs, page views, requests, bytes, and related
  request dimensions.
- The app does not currently store first-party visitor analytics.
- Cloudflare zone `uniques` are daily unique IP counts, not verified human visitors or all-time
  distinct people.
- Dwell time is not available from the current HTTP analytics view because Cloudflare only sees
  requests, not how long a browser tab remains open.

Questions to settle:

- Should Cloudflare Web Analytics / RUM be enabled for privacy-friendly page-level analytics and
  dwell-time-style engagement metrics?
- Does enabling Cloudflare Web Analytics require changing the `montrealmcm.ca` zone plan, or can it
  be enabled through the existing paid Cloudflare account setup?
- Should we avoid third-party analytics entirely and add a tiny first-party event endpoint only if
  audience signals become product-critical?

Likely work:

- check the Cloudflare dashboard for Web Analytics availability on `montrealmcm.ca`
- document whether Web Analytics has any plan gate or incremental cost for this account
- if enabled, verify what engagement metrics are actually exposed before making product decisions
  from them

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

Completed in `0.2.x`:

- durable anonymous identity uses a signed first-party browser cookie and stores only a hashed
  `owner_key` in D1
- listing and shop favourites moved behind the anonymous owner key
- old session favourite IDs migrate into the durable favourite tables when the browser returns

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

Completed in `0.2.x`:

- add D1/local schema for `listing_price_events`
- record discovered and changed source prices during refresh
- reuse existing `listing_availability_events` for availability history
- show recent price and availability history on listing detail pages when history rows exist
- apply D1 migration `0008_listing_price_events.sql` to production before deploying the
  history-reading app code; completed on 2026-05-24

Remaining follow-up:

- add price-drop or recently-sold labels only where they are useful and restrained
- consider merging price and availability events into one chronological timeline if event volume
  grows

### Discovery Improvements

Questions to settle:

- Which filters are genuinely useful once inventory grows?
- Should search be simple text search, SQLite/D1 FTS, or an external search service later?
- Are designer/maker filters good enough without canonical entities?
- Is the current i18n/l10n structure still clear enough as translated UI text, source-specific
  labels, and localized formatting grow?
- Are Jinja templates still easy to scan and safely modify, or should repeated listing/filter/shop
  fragments be split further?
- Is the Python application structure still contributor-friendly, especially around repository
  queries, source parsers, refresh orchestration, and presentation helpers?
- The `Recently added by source` sort label is misleading because it currently sorts by
  `last_seen_at`, which behaves more like "most recently seen on source" than a true source-side
  added date. Revisit the label and decide whether to rename it, remove it, or add a real
  source-order/source-added signal.

Likely work:

- saved filters
- better text search
- designer/maker cleanup
- richer shop pages
- collection-style browse pages such as teak storage, lounge chairs, dining sets, lighting
- compare mode for multiple saved items
- review and simplify i18n/l10n boundaries before translated strings and formatting rules spread
  further
- review Jinja template structure for readability, repeated fragments, and progressive HTMX
  behavior
- review Python module boundaries and naming so public contributors can understand ingestion,
  persistence, and rendering paths quickly

Completed in `0.2.x`:

- replace free-text Location filtering with a dropdown of current listing locations
- add curated bilingual synonym expansion for listing search so English/French terms such as
  `teak` / `teck`, `rosewood` / `palissandre`, and `sideboard` / `buffet` find the same inventory
- rank default search results by weighted field relevance so title/designer/category/material
  matches appear ahead of weaker description-only matches
- add broken-image fallbacks so upstream `403` / missing source images render as "Image not
  available" instead of browser broken-image icons
- make the shops index responsive at one, two, and three columns as viewport width allows
- add explicit shop addresses, direction links, and compact Leaflet location maps to the shops index
  and shop detail pages; Yardsale Vintage remains addressless until a public street address is found
- make the public listing grid lazy-load cards in 48-card batches. On 2026-05-24, the live initial
  HTML dropped from about 3.25 MB / 1,311 cards to about 145 KB / 48 cards, with a warmed response
  around 1.2 seconds and subsequent HTMX batches around 115 KB.

### Source Expansion

Current decision:

- Maison Singulier, Yardsale Vintage, and Chez Lamothe have source definitions and local ingestion
  paths.
- Habitat Mobilier, Green Wall Vintage, and Mostly Danish have source definitions and local
  ingestion paths as the first regional road-trip sources.
- Remove BOND Vintage from active sources for now because it has had zero active listings for a
  sustained period; keep the research notes so it can be reconsidered if live inventory returns.
- Treat Chez Lamothe as useful but slightly more coupled to Square Online internals than the
  Shopify/Cargo sources because it follows the public storefront API path observed in the browser.
- Keep Vintage Home Boutique later because it is outside the Ottawa/Quebec City/Townships pickup
  corridors.
- Regional research on 2026-05-15 identified Habitat Mobilier, Green Wall Vintage, and Mostly
  Danish as the first regional expansion set; those sources were implemented locally for `0.2.1`.
- Production ingestion on 2026-05-18 confirmed Habitat Mobilier and Green Wall Vintage are visible
  publicly, and Mostly Danish is ingesting through the planned rotating chunk path.
- A local source-quality check on 2026-05-29 found Mostly Danish active inventory heavily weighted
  toward dining chairs: 159 active local listings, 137 categorized as dining chairs. This appears to
  reflect the selected Shopify furniture feeds rather than a parser failure, but it can skew the
  MCM-first product feel if default discovery overweights that source/category.
- Deja Vu Meubles, Cornwall's Little Market, and A Fine Thing fit the regional taste/location
  criteria, but should wait because their public websites do not currently expose enough reliable
  item-level prices, details, and descriptions for ingestion on par with the existing shops.

Likely work:

- leave Deja Vu Meubles, Cornwall's Little Market, and A Fine Thing out of the next automated batch
  unless stable item feeds are verified
- monitor Chez Lamothe's Square storefront API path/cache version and add a fallback if it changes
- review Mostly Danish after more chunks ingest to decide whether its selected collections are too
  broad for the MCM-first product promise
- consider source/category weighting or narrower Mostly Danish collection selection if dining chairs
  dominate the default browse experience after reconciliation and more production chunks settle
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

### Remaining 0.2.x Release Shape

The likely remaining `0.2.x` releases are:

- `0.2.5`: implement the installable mobile web-app/PWA baseline. This is the actual build work
  behind the pinned iOS/Android direction already added to the plan: manifest, icons, theme colors,
  standalone display behavior, conservative service worker/offline fallback strategy, mobile
  safe-area spacing, and a first pass on touch targets and mobile detail-page ergonomics.
- `0.2.6`: accessibility and UI hardening. Run the planned W3C/WCAG-oriented audit and address the
  highest-impact issues around keyboard navigation, focus states, form labels, language switching,
  favourite controls, screen-reader behavior, branded 404 handling, and shop-detail directions
  parity.
- `0.2.7`: discovery/source cleanup. Revisit the misleading `Recently added by source` sort, review
  Mostly Danish weighting/source scope after production chunks settle, decide whether price-drop or
  recently-sold labels are worth adding, and revisit whether price/availability history should be
  presented as one timeline.
- `0.2.8`: conditional only. Use this for Cloudflare Web Analytics/RUM, a first-party analytics
  endpoint, or external uptime/alerting only if audience measurement or operational monitoring
  becomes important enough to justify a dedicated release.

The logical cutoff before `0.3.0` is when Montreal MCM feels dependable as a recurring personal
utility: durable favourites and saved searches work, listing history improves confidence, daily
refreshes are trustworthy, the app works well pinned on iOS/Android, accessibility has a baseline
pass, and source quality does not dilute the MCM-first promise.

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
- Are affiliate links, related ads, or paid shop placements compatible with trust?
- Which ad categories are relevant enough to feel useful rather than extractive, such as
  Article.com, IKEA, related furniture/home stores, local furniture repair, upholstery,
  moving/delivery, estate sales, or design services?
- Should ads be direct-sold/sponsorship placements first, or should the site test a network only
  after traffic is high enough and placement quality can be controlled?
- How should ads be labelled and separated from organic listings so source trust is preserved?

Likely work:

- trade-oriented saved boards
- private notes on saved items
- shareable shortlists
- analytics for outbound source clicks
- related-ad inventory research for home/design/furniture advertisers
- small, clearly labelled sponsorship or contextual-ad experiments outside listing cards
- careful monetization experiments only after the core catalogue is trusted

### UI Quality And Responsive Polish

Live design audit notes from 2026-05-20:

- On mobile listing detail pages, item identity appears too late because the large gallery and
  thumbnails push title, price, favourite action, and metadata below the first viewport.
- The mobile filter drawer is long enough that apply/reset controls are not immediately visible,
  making filtering feel heavier than it is.
- Complete the installable web-app/PWA work so Montreal MCM can be pinned on iOS and Android: web
  app manifest, appropriate icons, theme/background colors, standalone display behavior, service
  worker strategy, offline/fallback behavior, touch targets, browser-chrome-safe spacing, and
  notification readiness.
- Revisit saved-search alerts as part of the installable web-app/PWA work. Prefer anonymous Web
  Push tied to the existing durable owner key before adding email capture or real accounts.
- Listing image frames need a more intentional loading/unavailable state so slow, blocked, or
  missing source images do not create large blank wells.
- Shop index cards are becoming text-heavy at three columns; simplify card metadata before adding
  black-and-white shop maps.
- Shop detail pages currently expose `Get directions` as a Google Maps-only link. Revisit this so
  the detail page mirrors the shop listing card direction options and does not force one map
  provider.
- Add a branded 404 page with recovery paths back to listings/search instead of Flask's default
  unstyled 404.
- Strengthen interactive hierarchy for primary filter actions and favourite saved states without
  abandoning the restrained visual style.
- Review the UI against W3C/WCAG accessibility guidance, including semantic structure, keyboard
  navigation, focus states, color contrast, form labels, language switching, favourite controls, and
  screen-reader behavior.

### 0.3.x Success Criteria

The `0.3.x` line is successful when:

- the site has credible indexed discovery pages
- richer content improves buyer confidence rather than distracting from inventory
- normalized entities improve search and browsing quality
- any broader source or monetization strategy preserves trust

## 0.4.x Development: Assisted Relevance And Classification

The `0.4.x` line may explore model-assisted catalogue judgment after enough reviewed inventory
exists. This should remain future research if the product does not yet have enough examples,
review capacity, or clear user value.

### MCM Relevance Scoring

Questions to settle:

- Can the app collect enough admin-reviewed examples to distinguish "clearly MCM", "MCM-adjacent",
  "modern but not MCM", and "irrelevant" without encoding arbitrary taste as fact?
- Should a model use listing text only, images only, or combined evidence from title, description,
  source category, materials, designer/maker, era text, price, and image cues?
- How should explanations and provenance be shown so model output remains reviewable?
- Is this useful for source weighting and admin triage before it is safe for public filtering?

Likely work:

- build a reviewed training/evaluation dataset from existing listings and admin decisions
- store model-suggested MCM relevance confidence separately from source facts and manual overrides
- use the score first for admin review, source-scope tuning, and "MCM-adjacent" warnings rather than
  automatic public exclusion
- keep the option to move this work back to future research if simpler collection-level scope rules
  are enough

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

For `0.4.x`, consider assistive relevance scoring only if reviewed data and user value justify it.
