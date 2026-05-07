# Montreal MCM Listings Site Plan

Date: 2026-04-26
Updated: 2026-05-06

## Purpose

This document turns the research in [research.md](/Users/dlq/Developer/MCM%20Montreal/research.md) into a practical product and delivery plan.

This started as a planning document before implementation.

The project now has a working MVP foundation, so this document should be read as both:

- the original product plan
- the current roadmap from the codebase that now exists

## Current Build Status

Already implemented:

- listings feed with filters and sorting
- listing detail pages
- shop pages
- favourites for listings and shops
- browser-session favourites without user accounts
- freshness and availability labels
- bilingual English / French UI
- admin tools for refreshes, failures, overrides, and duplicate review

Currently active launch sources in code:

1. Morceau
2. Showroom Montreal
3. Montreal Moderne
4. Le Centerpiece

Morceau should be treated as Vintage-collection-only ingestion. Its broader furniture and
new-arrivals collections include current-production design inventory outside the app scope.

Still missing from the originally recommended first-wave source set:

1. Green Wall Vintage
2. Vintage Home Boutique
3. Maison Singulier

The biggest remaining product gaps versus the original roadmap are:

- saved searches
- alerts and notifications
- explicit price / availability history
- richer shop and discovery pages
- editorial / SEO content
- second-wave source expansion

Implementation note for source expansion: listing cards can omit repeated `Montreal, QC`
while all launch inventory is Montreal-local, but card-level location should come back when
adding Ottawa, Toronto, Quebec City, or other regional vintage shops that ship to Montreal.

## Product Goal

Create a site focused on resale and vintage mid-century modern furniture that is available in Montreal or can realistically be shipped to Montreal.

The product should make it easier than existing broad marketplaces to:

- discover local and Canada-friendly inventory
- compare pieces from multiple shops in one place
- track interesting items before they sell
- revisit saved pieces and shops
- understand whether a listing is likely available and shippable

## Core Product Thesis

The site should not try to out-marketplace `1stDibs`, `Chairish`, or `Pamono`.

Instead, it should win by being:

- Montreal-specific
- direct-source-first
- cleaner and more focused than general vintage marketplaces
- better at surfacing local Scandinavian / Danish / teak / walnut inventory
- better at showing current availability from smaller local shops

## Recommended Launch Scope

Start narrow.

Launch with:

- furniture only
- available items only
- direct-shop listings first
- Montreal shops plus a small set of Canada-friendly shops
- simple item cards and item detail pages
- favourites for users
- regular listing refreshes

Avoid at launch:

- lighting and decor as primary inventory categories
- broad marketplace ingestion beyond research/testing
- auctions
- dealer logins
- user-submitted listings
- price prediction or valuation tools

## Initial Source Scope

Launch sources:

1. Morceau
2. Showroom Montreal
3. Montreal Moderne
4. Green Wall Vintage
5. Vintage Home Boutique
6. Le Centerpiece

Second-wave sources:

1. Maison Singulier
2. Urbano Vintej
3. Banana Lab

Manual / later sources:

1. Chez Lamothe
2. Style Labo Antiquites
3. Trianon Boutique
4. Eco-Depot Montreal
5. Antiquites Van Horne
6. Bien Beau

## User Types

### 1. Casual Browser

Wants:

- a beautiful feed of interesting pieces
- the ability to browse by room or type
- simple price visibility
- easy click-through to seller

### 2. Serious Buyer

Wants:

- only currently available items
- ability to filter by price, dimensions, material, shop, and shipping
- favourites and saved searches
- confidence that the item is still live

### 3. Collector / Design Enthusiast

Wants:

- designer and maker names
- era and provenance details
- cleaner discovery than mass marketplaces
- rare and high-quality local inventory

### 4. Interior Designer / Trade User

Wants:

- efficient cross-shop discovery
- fast filtering
- ability to maintain private favourites lists
- confidence around dimensions, style, and availability

## User Experience Principles

- Make the site feel curated, not cluttered.
- Keep price and photo visible immediately.
- Make the path back to the original seller obvious.
- Clearly separate confirmed data from inferred data.
- Show availability freshness so users know how current a listing is.
- Do not overwhelm users with low-quality or irrelevant decor.

## Launch Features

### Listings Feed

Users should be able to browse all current listings in one place.

Each card should include:

- primary image
- title
- price
- currency
- shop name
- location
- category
- availability
- last checked date
- favourite button

### Filters

Launch filters should include:

- shop
- location
- price range
- category
- material
- designer / maker
- in stock / available
- ships to Montreal

Optional early filters if data quality is good enough:

- era
- dimensions
- colour

### Sorting

Users should be able to sort by:

- newest found
- most recently checked
- price low to high
- price high to low
- recently added by source

### Item Detail Page

Each item page should include:

- all available images
- full title
- price and currency
- shop name
- source link
- location
- category
- materials
- dimensions
- maker / designer
- era / approximate decade
- condition
- shipping note
- last checked timestamp
- favourite button

Helpful detail page labels:

- `Available`
- `Possibly sold`
- `Quote required for shipping`
- `Ships across Canada`
- `Montreal local source`

### Shop Pages

Each shop should have a profile page with:

- short description
- location
- shipping summary
- source site link
- active listing count
- categories carried
- notes about style focus

### Favourites

Users should be able to favourite:

- listings
- shops

Current implementation status:

- users can favourite listings and shops now
- favourites are stored in the browser session
- there is no real account-backed persistence yet

Minimum favourites behavior:

- save listing to account
- remove listing from account
- see all saved listings in one dashboard

Useful additions:

- saved shops page
- notification when a favourited item disappears
- notification when a favourited shop posts new inventory

### Saved Searches

Not required for day one, but highly recommended early.

Examples:

- `teak sideboard under $2000`
- `Hans Wegner chairs`
- `Montreal only`
- `dining table ships to Montreal`

### Freshness / Status Indicators

Every listing should have a freshness signal.

Recommended states:

- `Checked today`
- `Checked this week`
- `Needs refresh`
- `Unavailable / possibly sold`

This is important because resale inventory changes fast.

## Post-Launch Features

### Alerts

Users can subscribe to:

- new listings matching a saved search
- price changes
- listing status changes
- new inventory from a saved shop

### Collections / Editorial Curation

Examples:

- Best Teak Sideboards in Montreal
- Dining Sets Under $2,500
- Scandinavian Lounge Chairs
- Small-Space Pieces for Montreal Apartments

This would help differentiate from generic marketplaces.

### Compare Mode

Allow users to compare multiple items side-by-side by:

- price
- dimensions
- material
- shop
- shipping notes

### History / Change Tracking

For each listing, store:

- first seen date
- last seen date
- price changes
- availability changes

This helps:

- user trust
- debugging
- future editorial features

### Admin Review Queue

Internal tools should exist to review:

- failed refreshes
- duplicate listings
- suspicious price parsing
- broken images
- incorrect category assignments

## Listing Data Model

### Core Fields

- `listing_id`
- `source_shop_id`
- `source_shop_name`
- `source_listing_url`
- `title`
- `normalized_title`
- `price_raw`
- `price_value`
- `currency`
- `primary_image_url`
- `additional_image_urls`
- `availability_status`
- `shipping_scope`
- `ships_to_montreal`
- `last_seen_at`
- `last_checked_at`
- `first_seen_at`

### Descriptive Fields

- `category`
- `subcategory`
- `designer`
- `maker`
- `era`
- `materials`
- `dimensions_text`
- `width`
- `depth`
- `height`
- `condition_text`
- `location_text`
- `source_description`

### Operational Fields

- `ingest_source_type`
- `parse_confidence`
- `dedupe_group_id`
- `is_active`
- `is_featured`
- `manual_notes`

### Current Implementation Caveats To Revisit

- `subcategory` exists in SQLite but is not meaningfully populated yet.
- `width`, `depth`, and `height` exist in SQLite but are not yet extracted into structured numeric fields for most sources.
- `dimensions_text` is stored, but dimension parsing and normalization still need a dedicated hardening pass.
- `dedupe_group_id` exists in SQLite but is not yet actively assigned by the ingest pipeline.
- some descriptive fields remain source-dependent and incomplete, especially where the source pages do not expose structured metadata cleanly.
- listing-grid thumbnails need an image-normalization pass. CSS-only object fitting helps most items but does not consistently produce equal top/bottom/side whitespace for mixed source canvases, especially Le Centerpiece images. Future work should generate or cache normalized thumbnails with a consistent canvas and explicit crop/contain policy, potentially with source-specific rules.

## Shop Data Model

- `shop_id`
- `name`
- `website`
- `city`
- `province`
- `country`
- `is_montreal_local`
- `shipping_summary`
- `source_type`
- `crawl_priority`
- `notes`
- `active`

## Availability Rules

The product needs a simple, trustworthy listing-state model.

Recommended states:

- `available`
- `sold_out`
- `unknown`
- `removed`

Rules:

- if source explicitly says sold out, mark `sold_out`
- if listing disappears after prior availability, mark `removed`
- if page still exists but state is unclear, mark `unknown`

UI rule:

- hide `sold_out` and `removed` from main browse by default
- keep them in internal history

## Refresh Strategy

This is one of the most important product decisions.

### Target Refresh Frequency

For launch sources:

- high-priority Montreal shops: daily
- Canada-wide secondary shops: daily or every 48 hours

For second-wave sources:

- every 48 to 72 hours

For manual or unstable sources:

- weekly or manual review

### Refresh Workflow

1. discover listing URLs from source collections
2. fetch listing pages
3. parse structured fields
4. compare against prior snapshot
5. update item status
6. record changes
7. flag suspicious parse results for review

### What To Track On Refresh

- new item found
- price changed
- listing removed
- sold-out marker appeared
- image changed
- title changed

## Duplicate Handling

Duplicates may happen if:

- the same item appears on a direct site and a marketplace
- the same shop posts inventory to Facebook Marketplace under a personal or alternate seller account
- the same pair of chairs appears in multiple versions
- a shop republishes an item under a new URL

Initial dedupe strategy:

- prefer direct-shop listing over marketplace listing
- match by title similarity plus image similarity plus dimensions
- keep duplicates separate internally until confidence is high

User-facing rule:

- if duplicate confidence is low, do not merge automatically in the UI

## Category Strategy

Launch categories:

- sideboards / credenzas
- dressers / commodes
- dining tables
- dining chairs
- lounge chairs
- sofas
- coffee tables
- desks
- bookshelves / wall units
- nightstands
- beds / bedroom storage

Later:

- lighting
- rugs
- decor
- bar carts
- mirrors

## Search Strategy

Users should be able to search by:

- title
- designer
- maker
- material
- category
- shop

Common high-value keywords:

- teak
- rosewood
- walnut
- Danish
- Scandinavian
- Hans Wegner
- Grete Jalk
- Kai Kristiansen
- sideboard
- credenza
- wall unit

## Favourite System Plan

### Launch Version

- requires user account
- save listing
- remove listing
- view saved listings page

### Early Upgrade

- save shops
- tag favourites by room or project
- archive sold favourites

### Notification Upgrade

- email when favourited listing goes unavailable
- email when price changes
- email when saved search gets a new match

## Accounts

At minimum, accounts should support:

- email login
- saved favourites
- saved shops
- saved searches
- alert preferences

Current implementation status:

- not implemented as a real user-facing system yet
- the database schema has a `users` table, but the app does not currently expose account creation, login, or persisted user-specific favourites

Optional later additions:

- project boards
- design-trade profile
- private notes on saved items

## Admin / Internal Tools

Internal tools matter because source quality will vary.

Must-have admin features:

- source list and crawl health
- failed page review
- listing inspection page
- duplicate review queue
- manual override for availability
- manual override for category
- manual featured-listing selection

Nice-to-have admin tools:

- price change report
- new listings digest
- source coverage dashboard

## Editorial / Content Layer

The site should not only be a feed.

Editorial content can improve SEO, retention, and brand differentiation.

Good content types:

- neighbourhood furniture guides
- designer explainers
- “what to look for” authenticity guides
- new arrivals roundups
- room-type buying guides

Examples:

- Where to Find Teak Sideboards in Montreal
- Best Mid-Century Dining Sets This Week
- How to Tell if a Piece is Real Danish Modern

## SEO / Discovery Plan

Target pages:

- listings
- shop pages
- category pages
- city-specific browse pages
- editorial guides

Likely useful page types:

- `/shops/morceau`
- `/categories/sideboards`
- `/materials/teak`
- `/designers/hans-wegner`
- `/montreal`

Important SEO principles:

- unique titles and meta descriptions
- canonical source links where appropriate
- avoid thin duplicate marketplace-style pages
- include structured listing details cleanly

## Analytics Plan

Track:

- listing views
- source click-throughs
- favourites added
- saved search creation
- shop page views
- category filter usage
- source-level outbound clicks

Questions analytics should answer:

- which shops generate the most user interest
- which categories are most popular
- whether users prefer local shops over Canada-wide sources
- whether favourites convert to outbound clicks

## Monetization Options

Do not let monetization complicate launch.

Possible later models:

- affiliate-like referral arrangements with shops
- featured shop placements
- sponsored collections
- trade membership with alerts and boards

Launch recommendation:

- no monetization dependency
- focus on product quality and inventory freshness first

## Risks

### 1. Source Fragility

Small shops may redesign pages or remove listing content.

Mitigation:

- start with a small source set
- maintain source-specific notes
- build internal review workflow

### 2. Inventory Staleness

Users will lose trust fast if sold items stay live.

Mitigation:

- daily refreshes for local priority sources
- strong freshness labels
- hide stale items by default

### 3. Mixed Inventory

Some sources mix furniture, decor, and non-core objects.

Mitigation:

- narrow launch taxonomy
- prefer furniture-only collections first

### 4. Ambiguous Shipping

Many shops use quote-based shipping.

Mitigation:

- represent shipping as a confidence signal, not a promise
- use labels like `quote required`

### 5. Duplicate Items Across Sources

Mitigation:

- prefer direct source
- review duplicates conservatively

## Proposed Phases

### Phase 0: Definition

Goal:

- finalize scope and feature priorities

Deliverables:

- research source list
- product plan
- feature scope
- source priority order

### Phase 1: MVP Listings Product

Goal:

- working browseable catalog with direct-shop sources only

Includes:

- source ingestion for priority shops
- listing cards
- item pages
- filters
- shop pages
- favourites
- manual admin review tools

Success criteria:

- daily-refreshed local inventory
- users can save listings
- users can click through confidently to seller

Current status:

- substantially implemented
- should now focus on hardening parser reliability, refresh quality, and availability-state trust
- should resolve whether launch remains strictly furniture-first or formally includes some lighting / decor

### Phase 2: Retention Features

Goal:

- give users reasons to come back

Includes:

- saved searches
- alerts
- price and availability change tracking
- improved shop profiles

Success criteria:

- repeat visits
- meaningful favourite usage
- alert subscriptions

Recommended next build priority:

- this is now the clearest missing layer after Phase 1 hardening
- saved searches and change tracking should come before a broad source expansion

### Phase 3: Content and Expansion

Goal:

- strengthen discovery and SEO

Includes:

- editorial content
- second-wave sources
- compare view
- curated collections

Recommended interpretation now:

- first complete the missing first-wave direct shops
- then expand into richer browse pages, editorial pages, and carefully chosen second-wave sources

### Phase 4: Broader Marketplace Strategy

Goal:

- decide whether marketplace overlap is worth ingesting

Includes:

- explicit Facebook Marketplace recheck for current and candidate sources
- optional marketplace inclusion
- duplicate-preference rules
- direct-vs-marketplace source badges

Recommendation:

- only do this after the direct-shop product works well

## Delivery Order Recommendation

Given the current codebase, the best next order is:

1. harden the existing parsers and refresh reliability
2. tighten availability handling and duplicate-review quality
3. decide whether launch stays furniture-only or accepts some lighting / decor
4. add Green Wall Vintage, Vintage Home Boutique, and Maison Singulier
5. implement saved searches
6. add explicit price and availability change tracking
7. add alerts and notification preferences
8. deepen shop, category, material, and designer discovery pages
9. add editorial content and analytics
10. expand to Urbano Vintej and Banana Lab
11. evaluate marketplace ingestion only after the direct-source product is strong

## MVP Success Definition

The MVP is successful if:

- it aggregates live-looking inventory from priority sources
- users can quickly browse by category and price
- users can favourite listings
- users trust the freshness labels
- the site feels meaningfully more focused than 1stDibs or Chairish for Montreal-oriented MCM discovery

For the current build, "MVP success" should also mean:

- parser failures are understandable and reviewable
- the active direct-shop sources feel dependable enough to use repeatedly
- the site is ready for retention features rather than still fighting basic ingestion trust issues

## Bottom Line

The best version of this product is not a giant marketplace clone.

It is a tight, well-curated Montreal-first discovery layer built on direct-shop inventory, with:

- strong listing freshness
- clean filters
- useful favourites
- a small, high-quality source list

The most important operational feature is not visual polish.

It is reliable listing refresh and availability tracking.
