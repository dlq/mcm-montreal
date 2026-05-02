# Montreal MCM Future Steps

Date: 2026-04-27

## Where The Project Stands Now

The codebase is no longer at the planning stage described in `plan.md`.

There is already a working Phase 1-style product in place with:

- a Flask app backed by SQLite
- listings feed with filters and sorting
- listing detail pages
- shop index and shop detail pages
- favourites for listings and shops
- lightweight email-based local session login
- freshness and availability labels
- bilingual English / French UI
- admin tools for refreshes, failures, manual overrides, and duplicate review

The current source ingestion layer is implemented for four direct shops:

1. Morceau
2. Showroom Montreal
3. Montreal Moderne
4. Le Centerpiece

The app also includes seed data for additional shops, but those sources are not yet active in the live source definitions.

## What From The Plan Is Still Incomplete

Compared with `plan.md` and `research.md`, the main remaining gaps are:

- the launch source set is still smaller than the originally recommended first wave
- saved searches are planned but not implemented
- alerts and notifications are not implemented
- price-change and availability-change history are not stored as a first-class feature
- shop profiles are useful but still fairly lightweight
- editorial / SEO landing pages are not implemented
- second-wave source expansion has not started
- broader marketplace strategy remains intentionally deferred

There is also a scope decision to clean up:

- the original launch recommendation said to stay furniture-first, but the current source/category setup already allows some lighting and decor inventory to appear

## Recommended Next Steps

### 1. Stabilize Phase 1 Before Expanding

Treat the current app as a real MVP and harden the ingestion loop before adding too much new scope.

Do next:

- verify each active parser against live source markup and reduce reliance on seed fallback where possible
- review duplicate detection quality and define what should be manual-only vs auto-grouped
- tighten availability handling for `available`, `sold_out`, `unknown`, and `removed`
- decide whether lighting and decor should be hidden at launch or formally accepted into Phase 1

### 2. Complete The Original Launch Source Set

The research-backed first-wave source list was broader than the four currently active shops.

Next additions should be:

1. Green Wall Vintage
2. Vintage Home Boutique
3. Maison Singulier

After that:

1. Urbano Vintej
2. Banana Lab

For each new source:

- add a `SourceDefinition`
- build a source-specific parser
- verify shipping language for Montreal eligibility
- map categories cleanly into the launch taxonomy
- confirm sold / unavailable behavior

### 3. Add Retention Features

This is the biggest product gap between the implemented MVP and the planned roadmap.

Build next:

- saved searches
- alert preferences per user
- notifications for new matches
- notifications for price changes
- notifications for availability changes
- notifications for new listings from saved shops

This is the clearest bridge from a useful catalog to a product people return to.

### 4. Add Real Change Tracking

The current schema already stores `first_seen_at`, `last_seen_at`, and `last_checked_at`, which is a good base.

The next step is to record historical events explicitly:

- price change log
- availability change log
- listing removed / relisted events
- source parse anomalies worth review

That will support alerts, trust, debugging, and later editorial features.

### 5. Deepen Shop And Discovery Pages

The product thesis is stronger when the site feels curated rather than just aggregated.

Next improvements:

- richer shop profiles
- category landing pages
- material pages such as teak and rosewood
- designer / maker browse pages
- Montreal-specific browse pages
- better internal linking between listings, shops, categories, and designers

### 6. Build The Editorial Layer

This was a major differentiator in `plan.md` and has not started yet.

Good first content formats:

- weekly new arrivals roundups
- Montreal shop guides
- category guides such as teak sideboards or dining sets
- designer explainers
- authenticity / buying guides

This work should happen after the core ingestion and retention loops are dependable.

### 7. Add Analytics And Product Feedback Loops

Before expanding too far, instrument the basics:

- listing views
- outbound clicks to source sites
- favourites added
- saved search creation
- filter usage
- shop page engagement

This will show which sources and categories are actually valuable.

### 8. Revisit Marketplace Expansion Later

`research.md` and `plan.md` were right to defer `1stDibs`, `Chairish`, and `Pamono`.

Only revisit that work after:

- the direct-shop ingestion layer is stable
- the first-wave sources are fully live
- duplicate handling is trustworthy
- retention features are in place

## Suggested Execution Order

1. harden current parsers and refresh reliability
2. resolve the furniture-only vs broader-inventory scope decision
3. add Green Wall Vintage, Vintage Home Boutique, and Maison Singulier
4. implement saved searches and change-history tables
5. add alerts / notifications
6. improve shop, category, material, and designer discovery pages
7. add editorial content and analytics
8. expand to Urbano Vintej and Banana Lab
9. evaluate marketplace ingestion only after the direct-source product is strong

## Bottom Line

The next chapter should not be a full rewrite.

The project already has a solid MVP foundation. The best path forward is to:

- harden ingestion
- finish the first-wave direct-source coverage
- add retention features
- then expand discovery and content

That keeps the product aligned with the original Montreal-first thesis while building on what already works.
