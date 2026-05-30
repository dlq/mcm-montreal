# Montreal MCM Resale Research

Date: 2026-04-26
Updated: 2026-05-15

## Goal

Build a site that lists resale and vintage mid-century modern furniture pieces available to buyers in Montreal, with:

- item photo
- item price
- link back to the source listing
- only sources that can realistically sell and ship to Montreal, or are already in Montreal

This document is intentionally research-only. It is meant to answer:

1. What shops and marketplaces are worth tracking?
2. Which ones look easiest to spider first?
3. Which ones are better handled later or manually?

## Current Project Status Note

This document began as pre-build research, but the project now has a working MVP codebase.

What is already implemented in code:

- Flask + SQLite application
- listings feed with filters and sorting
- listing detail pages
- shop index and shop detail pages
- favourites for listings and shops
- browser-session favourites without a real account flow yet
- freshness and availability labels
- bilingual English / French UI
- localized parsed price display independent of source language
- default sans-serif item-title and wordmark styling while the display-font direction is reconsidered
- admin review tools for refreshes, failures, overrides, and duplicate inspection

What is currently live in the source layer:

1. Morceau
2. Showroom Montreal
3. Montreal Moderne
4. Le Centerpiece
5. Maison Singulier
6. Yardsale Vintage
7. BOND Vintage
8. Chez Lamothe

This means the research priority is no longer just "what should we build first." It is now also
"which sources are stable enough to keep refreshing, and what caveats should the parsers carry?"

## Recommendation History And Current Status

The original research recommendation was to start with a small set of stores that already have:

- public item detail pages
- clear prices on-page
- item photos on-page
- explicit Canada-wide, Montreal, or international shipping language

Original first spider targets:

1. Morceau Montreal
2. Showroom Montreal
3. Montreal Moderne
4. Green Wall Vintage
5. Vintage Home Boutique
6. Le Centerpiece

Original secondary expansion targets:

1. Urbano Vintej
2. Banana Lab
3. Maison Singulier
4. 1stDibs
5. Chairish
6. Pamono

Original manual / later-review targets:

1. Chez Lamothe
2. Style Labo Antiquites
3. Trianon Boutique
4. Eco-Depot Montreal
5. Antiquites Van Horne
6. Bien Beau

Current implementation status:

- Morceau, Showroom Montreal, Montreal Moderne, and Le Centerpiece became the original launch
  sources.
- Maison Singulier, Yardsale Vintage, BOND Vintage, and Chez Lamothe were added next as the first
  local expansion sources.
- Green Wall Vintage, Vintage Home Boutique, Urbano Vintej, Banana Lab, 1stDibs, Chairish, and
  Pamono remain later candidates rather than current active sources.
- Chez Lamothe graduated from manual/later-review to automated ingestion after the Square Online
  storefront API path was verified.

## Recent Local Source Expansion

As of 2026-05-15, the current expansion stays local-first. For Montreal and agglomeration-area
shops, local pickup or local delivery is enough; Canada-wide shipping is not required.

If the product later expands beyond the Montreal agglomeration, or if traffic materially shifts
toward users outside Montreal, shipping requirements should be revisited before adding more
non-local sources.

### Implemented Local Expansion Set

1. Maison Singulier
2. Yardsale Vintage
3. BOND Vintage
4. Chez Lamothe

Reason:

- they preserve the Montreal-first thesis better than jumping to Ottawa, Toronto, or broader
  Canada-friendly shops
- they are closer in caliber and curation to the current four active sources
- they should add local discovery value without turning the product into a broad resale marketplace

### Implementation Readiness

Verified local ingestion on 2026-05-14:

1. Maison Singulier
2. Yardsale Vintage
3. BOND Vintage
4. Chez Lamothe

Findings:

- Maison Singulier has clean Shopify collection JSON for current furniture-like collections. Archive
  collections are present on the site and should remain excluded.
- Yardsale Vintage can be crawled through Cargo's public page/filter API. The current Shop gallery
  exposes title, price, image, description, and detail URLs; the Archive gallery is separate and
  should remain excluded.
- BOND Vintage has Shopify collection data, but the visible furniture-like inventory is currently
  sold out. The source parser works, but existing refresh semantics skip brand-new sold-out items,
  so it may contribute zero public listings until inventory returns.
- Chez Lamothe exposes a Square Online storefront products API used by the public shop grid. The
  captured endpoint includes prices, images, descriptions, detail URLs, and out-of-stock badges.
- Chez Lamothe originally looked slower and less complete through sitemap/product-page metadata, but
  the storefront API is a better ingestion path and avoids contact-for-details pricing when a price
  is shown online.

### Explicitly Deferred From The Montreal/Agglomeration Expansion

1. EcoDepot Montreal
2. Trianon Boutique
3. Vintage Home Boutique
4. Banana Lab
5. 1stDibs
6. Chairish
7. Pamono

Reason:

- EcoDepot is relevant locally, but inventory is broad and thrift-like enough that it could weaken
  focus unless added with careful category filtering.
- Trianon is high caliber, but the emphasis is French antiques / 18th-century decorative arts rather
  than the core MCM furniture product.
- Vintage Home Boutique remains a useful Canada-friendly candidate, but it is not local enough for
  the next regional expansion step.
- Banana Lab should not be treated as Montreal-local based on the latest review.
- Large marketplaces remain a later strategy because they introduce duplication, crawl complexity,
  and weaker direct-source differentiation.

## Regional Source Expansion Research

Checked on 2026-05-15. The next expansion beyond Montreal should still feel road-trip local:
Ottawa, Quebec City, Sherbrooke, the Eastern Townships, Lanaudiere, Laurentides, Outaouais, and
shops on the routes to those places. For this stage, a source can qualify if it either ships to
Montreal or is an easy 2-3 hour pickup from Montreal.

### Selected Next Regional Expansion Set

1. Habitat Mobilier, West Brome / Eastern Townships
2. Green Wall Vintage, Ottawa
3. Mostly Danish, Ingleside / Ottawa corridor

Reason:

- Habitat Mobilier is the cleanest Eastern Townships fit. It focuses on restored Scandinavian and
  Mid-Century furniture, with teak, walnut, and rosewood inventory; the shop page exposes item
  names and sold markers; the tourism listing says shipping is available for most of Quebec; the
  contact page says West Brome is about one hour from Montreal.
- Green Wall Vintage remains a strong crawl candidate now that the scope can extend past the
  Montreal agglomeration. It has visible Shopify inventory, prices, MCM categories, an Ottawa-area
  location, and delivery across Canada and the United States.
- Mostly Danish is high-caliber and regional enough for pickup because the site now lists Ingleside,
  Ontario, which sits on the Montreal-Ottawa corridor. The site exposes product pages, designers,
  prices, sold states, and categories, but the inventory mixes vintage Scandinavian/MCM, outdoor
  teak, Oriental antiques, and services, so category filtering matters.

### Good-Fit Regional Leads Without Enough Item Data

1. Deja Vu Meubles, Quebec City
2. Cornwall's Little Market, Cornwall / Montreal-Ottawa corridor
3. A Fine Thing, Ottawa
4. Urban Artifacts, Ottawa
5. General Chicken Antiques, Ottawa
6. ReFind Originals, Ottawa
7. Yardley's Antiques, Ottawa
8. The Modern Shop, Ottawa
9. Turquoise's Treasures, likely Montreal-area

Reason:

- Deja Vu Meubles is the best Quebec City lead found so far. Current evidence describes a St-Roch
  shop with vintage furniture/decor from roughly the 1930s-1980s, local delivery, and online/social
  shopping, but crawlability still needs verification because the primary public site was not
  accessible in this pass.
- Cornwall's Little Market is a very strong taste fit on the Montreal-Ottawa road: reporting
  describes MCM furniture/accessories from the 1930s-1980s, including Scandinavian, American, and
  Canadian designers, and notes customers drive from Montreal and Ottawa. It appears likely
  Facebook-first, so it is probably profile/manual-first unless a stable catalog is found.
- A Fine Thing in Ottawa explicitly mentions Danish teak furniture, a Mid-Century section, and
  delivery to Montreal, Quebec City, Toronto, and southern Ontario. The site has many pictures but
  does not appear to expose enough item-level detail, prices, and descriptions for source ingestion
  on par with the current active shops.
- Urban Artifacts has a Shopify site and says it carries Mid-Century ceramic, glass, furniture, and
  art, but it may skew toward smaller objects, uses USD pricing, and says website items are not
  available in the physical store.
- General Chicken Antiques and ReFind Originals have strong Ottawa furniture-store mentions in local
  guides, but a stable first-party item feed was not verified in this pass.
- Yardley's has a broad classic lighting/furniture/antiques site with categories, but the visible
  positioning is broader antiques rather than focused MCM.
- The Modern Shop is design-relevant and buys vintage MCM/Scandinavian pieces, but it appears
  primarily new/authentic modern retail rather than resale inventory.
- Turquoise's Treasures mentions vintage, MCM, retro, and furniture, but the fit looks broader and
  more mixed than the strongest candidates.

### Regions With Weak Evidence So Far

Lanaudiere and Laurentides did not produce a same-caliber MCM direct-shop candidate in this pass.
The strongest search results were broad antiques, auctions, Kijiji-style sellers, or thrift/circular
economy sources:

- Antiquite S.G. in Terrebonne appears focused on Quebec/Canadian antiques, pine, folk art, and
  vintage objects rather than MCM furniture.
- Encans des Laurentides is an auction source for vintage/antiques/collectibles, but not a focused
  direct furniture shop and not a clean MCM catalog.
- Eastern Townships tourism lists several good vintage/antique stops, but most beyond Habitat skew
  country, Victorian, pre-1900, circular economy, or broad thrift.

### Recommended Regional Implementation Order

1. Habitat Mobilier
2. Green Wall Vintage
3. Mostly Danish

Implementation stance:

- Start with Habitat because it is the closest conceptual fit and has a public shop page with
  current and sold inventory visible.
- Then add Green Wall Vintage because the Shopify structure should be close to existing collection
  parsers and shipping to Montreal is clear.
- Then spike Mostly Danish with strict category filtering and sold/outdoor/new-vs-vintage checks.
- Do not add Deja Vu Meubles, Cornwall's Little Market, or A Fine Thing in this implementation
  batch unless a stable item feed with prices, item details, and item URLs is found.

Implementation findings on 2026-05-18:

- Habitat Mobilier exposes Squarespace store JSON at `/boutique?format=json-pretty`, including
  product ids, URLs, images, descriptions, variant stock, and prices. The live parser treats only
  in-stock variants as current public inventory and parsed 21 current listings locally.
- Green Wall Vintage exposes Shopify product JSON through `/collections/all/products.json`. The
  live parser filters non-furniture products and parsed 39 furniture listings locally.
- Mostly Danish exposes Shopify collection JSON. The implementation uses selected furniture
  collections (`wm-seating`, `wm-tables`, `wm-sideboards`, `wm-storage`, `wm-office`) and excludes
  outdoor, Oriental, accents, and archive collections. A local refresh found 200 source rows and
  kept 159 active public listings after existing sold-out semantics skipped brand-new sold rows.
- A deeper collection-size check found 1,306 source rows across the selected Mostly Danish
  collections, so production ingestion should be gradual rather than a single monolithic source
  refresh. The Worker now rotates through 5 of 30 collection-page chunks per refresh run.
- Mostly Danish does expose narrower Shopify category pages, but not a clean era taxonomy that
  separates "MCM" from later "modern" inventory. Public navigation includes broad furniture
  collections (`wm-seating`, `wm-tables`, `wm-sideboards`, `wm-storage`, `wm-office`) plus
  subcollections such as `wm-seating-armchairs-recliners`, `wm-seating-dining`,
  `wm-seating-sofas`, `wm-tables-coffee`, `wm-tables-dining`,
  `wm-storage-buffets-hutches`, `wm-storage-cabinets-bookcases`,
  `wm-storage-dressers`, `wm-office-chairs`, `wm-office-desks-conference-tables`,
  and `wm-office-storage-shelving`. It also has `featured`, `solid-teak`,
  `arne-jacobsen`, and `wm-collectors-items` collections that may be more aligned with the
  site's thesis, but those are not complete furniture-type feeds.
- A 2026-05-20 count of Mostly Danish collection pages found the current broad feeds remain large:
  `wm-seating` 566, `wm-tables` 269, `wm-sideboards` 195, `wm-storage` 142, and `wm-office` 134.
  More specific candidates include `featured` 23, `solid-teak` 136, `arne-jacobsen` 10,
  `wm-collectors-items` 141, `wm-storage-buffets-hutches` 39, `wm-storage-dressers` 26,
  `wm-tables-coffee` 108, and `wm-tables-dining` 213. The collection names are still imperfect:
  sampled "Mid-Century Modern Armchairs & Recliners" products included late-20th-century and
  21st-century items, so any tighter scope should prefer collection-level inclusion/exclusion or
  source weighting rather than subjective item-by-item MCM judgments.

## Research Questions That Still Matter

The build has answered the "is this product worth prototyping?" question. The main research questions still worth validating are now:

1. Which active source parsers are stable enough to rely on without frequent seed fallback?
2. Do Maison Singulier and BOND Vintage keep enough current, non-archive inventory online to remain
   useful active sources?
3. Do Yardsale Vintage and Chez Lamothe keep their current public data paths stable enough for
   automated refreshes?
4. Which sources mix in too much lighting or decor for a furniture-first launch?
5. Which sources are most likely to create duplicate inventory if marketplace expansion happens later?

## What To Capture Per Item

Minimum fields:

- `source_shop`
- `source_city`
- `source_url`
- `item_url`
- `title`
- `price`
- `currency`
- `primary_image_url`
- `availability`
- `shipping_scope`
- `shipping_note`

Nice-to-have fields:

- `designer_or_maker`
- `era`
- `dimensions`
- `materials`
- `condition`
- `category`
- `location`

## Best Sources To Start Spidering

### 1. Morceau Montreal

- URL: https://www.morceau.ca/
- Why it matters: Montreal-based, directly aligned with the niche, clearly lists vintage inventory online.
- Shipping signal: homepage says "INTERNATIONAL SHIPPING AVAILABLE ON ALL ITEMS."
- Crawlability: strong. Public product and collection pages with visible prices and images.
- Notes:
  - Vintage collection page is visible: https://www.morceau.ca/collections/vintage
  - This looks like one of the strongest launch sources.
  - As of 2026-05-07, ingestion should use only the Vintage collection. Broader Morceau
    collections include current-production design pieces that do not fit the vintage/MCM scope.

### 2. Showroom Montreal

- URL: https://www.showroommtl.com/
- Why it matters: local Montreal MCM specialist with strong Scandinavian and restored-vintage focus.
- Local signal:
  - store/about pages describe a Montreal shop focused on 1950s-1970s modern furniture, lighting, and decor
  - local directory listing places it in Hochelaga-Maisonneuve
- Crawlability: strong. The `Nouveautés` page exposes item images, item names, dimensions, and often prices in-page.
- Notes:
  - Example inventory page: https://www.showroommtl.com/nouveaute
  - Many listings are directly readable on-page without needing a private checkout flow.
  - Some entries say "Contactez nous pour les détails" rather than showing a price, so price completeness may vary.
  - The app now localizes that fallback as `Contact us for details` / `Contactez-nous pour les détails` for user-facing display while preserving the raw source text for provenance.
  - Showroom price suffixes seen so far include `/ 6`, `/ 4`, `/ paire`, `ch.`, and `/ l'ens.`. The app treats numeric suffixes as total prices for a set count, `paire` as pair, `ch.` as each, and `l'ens.` as the set.

### 3. Montreal Moderne

- URL: https://www.montrealmoderne.com/
- Why it matters: local Montreal Scandinavian/MCM specialist and highly relevant to the thesis of the site.
- Local signal:
  - homepage says the shop has offered Scandinavian furniture in Montreal since 2007
  - physical location shown on Sainte-Catherine Est in Montreal
- Crawlability: strong. The `Nouveautés` page shows titles, images, prices, and sold-out states directly on-page.
- Notes:
  - Example inventory page: https://www.montrealmoderne.com/nouveaut%C3%A9s
  - Especially useful because availability is visible as either a price or `Rupture de stock`.
  - This is one of the best local-first sources in the research set.

### 4. Green Wall Vintage

- URL: https://www.greenwallvintage.ca/
- Why it matters: explicitly markets to Montreal customers and sells vintage MCM inventory.
- Shipping signal:
  - Montreal page: https://www.greenwallvintage.ca/pages/mid-century-modern-furniture-in-montreal
  - Delivery page says delivery is offered across Canada and the United States: https://www.greenwallvintage.ca/pages/delivery
- Crawlability: strong. Homepage shows item cards with titles and prices. Clear collection structure.
- Notes:
  - Likely good early source for Canadian inventory that can ship to Montreal.

### 5. Vintage Home Boutique

- URL: https://vintagehomeboutique.ca/
- Why it matters: large vintage MCM inventory, established online seller, strong Canadian relevance.
- Shipping signal:
  - About page says "Canada-wide delivery options": https://vintagehomeboutique.ca/pages/about-us
  - Product pages include "Canada Wide Shipping" and delivery notes.
- Crawlability: strong. Product pages are public and price-forward.
- Example item pages:
  - https://vintagehomeboutique.ca/products/erik-ole-jorgensen-for-tarm-stole-mid-century-teak-armchairs
  - https://vintagehomeboutique.ca/products/danish-mid-century-modern-teak-bedside-chests

### 6. Le Centerpiece

- URL: https://lecenterpiece.com/
- Why it matters: Montreal-based, high-quality curated vintage inventory.
- Shipping signal:
  - About page says "Montreal — Worldwide": https://lecenterpiece.com/pages/about-us
  - Terms say oversized or heavy items require a shipping quote before purchase: https://lecenterpiece.com/pages/terms-and-policies
  - Shipping quote page exists: https://lecenterpiece.com/pages/shipping-quote-inquiry
- Crawlability: medium to strong. Inventory is visible online with prices, but shipping may need quote-based interpretation.
- Notes:
  - Good source for aspirational / premium inventory.
  - Shipping eligibility to Montreal is likely fine, but cost may not be known without quote.

## Strong Additional Montreal Source

### Maison Singulier

- URL: https://maisonsingulier.com/
- Why it matters: Montreal-based vintage furniture and home goods shop focused on Modernist, Brazilian, Mid-Century, and Postmodern design.
- Local signal:
  - about page says it is based in Montreal
  - store page lists a Montreal address and appointment-based visits
- Crawlability: medium to strong. Public collection and product pages exist, with visible images, descriptions, and pricing behavior.
- Notes:
  - collection page exists: https://maisonsingulier.com/collections
  - seating collection shows live prices on some items: https://maisonsingulier.com/collections/seating
  - large-item product pages explicitly instruct buyers to request a shipping quote, which is fine for the project if quote-based Montreal shipping is allowed
  - local ingestion verified 21 live listings with images and prices on 2026-05-14
  - implementation avoids archive collections

### Yardsale Vintage

- URL: https://yardsale-vintage.com/
- Why it matters: Montreal studio focused on restored, one-of-a-kind vintage furniture with a strong
  fit for the curated local thesis.
- Local signal:
  - about page says the studio operates in Montreal
  - pieces can be viewed in person by appointment
  - public site currently lists the furniture shop, email, and Instagram handle, but no street
    address
- Delivery signal:
  - FAQ/about pages say shipping is available across Canada and the United States by quote
  - for this project, local appointment/pickup or local delivery would be enough even without
    Canada-wide shipping
- Crawlability: medium. The site is Cargo-based and the current Shop gallery can be fetched through
  Cargo's public page/filter API.
- Notes:
  - local ingestion verified 11 current Shop-gallery listings with images and prices on 2026-05-14
  - Archive gallery should remain excluded
  - keep `street_address` empty unless a public street address is found; use the source note
    "No public street address found; contact the shop for pickup or appointment details."

### BOND Vintage

- URL: https://bondvintage.com/
- Why it matters: Montreal shop selling vintage modern furniture and home accessories from multiple
  periods and countries.
- Local signal:
  - about page lists the shop on boulevard Saint-Laurent in Montreal
- Crawlability: medium to strong technically because it appears Shopify-based.
- Notes:
  - collection page shows product cards, prices, and sold-out states
  - local parser verified 9 visible collection cards on 2026-05-14
  - all visible items were marked sold out / `Épuisé`
  - two visible cards were poster/art items and should be skipped for furniture-first ingestion
  - existing refresh behavior skips brand-new sold-out records, so BOND may have an active shop row
    with zero public listings until active inventory returns

### Chez Lamothe

- URL: https://www.chezlamothe.com/
- Why it matters: local Montreal source for restored Mid-Century furniture, especially teak,
  Scandinavian, Danish, and Canadian pieces.
- Local signal:
  - third-party listings and writeups place it in Montreal and describe it as a restored MCM
    furniture shop
- Crawlability: medium to strong. The public shop grid uses a Square Online storefront API that
  exposes product data, prices, images, and out-of-stock badges.
- Notes:
  - high-caliber local source and should be part of the product
  - local ingestion initially verified sitemap/product-page metadata on 2026-05-14, but that path
    omitted prices
  - browser network inspection on 2026-05-14 confirmed the price-bearing storefront endpoint:
    `https://cdn5.editmysite.com/app/store/api/v28/editor/users/131647755/sites/345976907244501379/products`
  - storefront API responses include `price.low`, `images.data`, `absolute_site_link`, and
    `badges.out_of_stock`

### 5. Urbano Vintej

- URL: https://www.urbanovintej.ca/
- Why it matters: vintage-oriented catalog with visible inventory and a Canada-wide message.
- Shipping signal: homepage says "DELIVERY ACROSS CANADA."
- Crawlability: medium. Public item titles and prices are visible on-page.
- Notes:
  - Worth including in phase 1 if item pages are consistent enough.
  - Should be reviewed quickly before relying on it as a major source.

### 6. Banana Lab

- URL: https://www.bananalab.ca/
- Why it matters: direct vintage / consignment / MCM-adjacent catalog.
- Shipping signal: shipping page says they offer local pickup, local delivery, and shipping to Canada and other countries: https://www.bananalab.ca/shipping
- Crawlability: medium. Shipping evidence is strong; item-page consistency should be checked during implementation.
- Current status:
  - defer for now
  - latest review suggests it should not be treated as Montreal-local for the next expansion batch

## Good Secondary Marketplaces

These are useful because they already solve discovery, but they are broader and may be noisier than direct-shop sources.

### 1stDibs

- URL: https://www.1stdibs.com/
- Shipping signal: support docs say they offer insured delivery to "just about anywhere in the world."
- Canada signal:
  - Canada furniture listings: https://www.1stdibs.com/locations/canada-north-america/furniture/
- Crawlability: medium. Huge catalog, but likely more complexity and stronger anti-bot risk than direct shops.
- Good use:
  - later expansion
  - dealer discovery
  - filtering to Canada-located items first

### Chairish

- URL: https://www.chairish.com/
- Shipping signal: help docs say Chairish only facilitates sales within the U.S. and Canada.
- Crawlability: medium to low for a first pass. Good marketplace, but likely noisier and more operationally complex than direct-shop sources.
- Good use:
  - phase 2 marketplace expansion
  - only if we confirm clean listing pages and stable selectors

### Pamono

- URL: https://www.pamono.ca/
- Shipping signal: homepage says "Worldwide Shipping."
- Crawlability: medium. Big catalog, global, likely useful later.
- Good use:
  - phase 2 or 3
  - collectible European inventory

## Montreal Shops Worth Tracking But Not Currently Active

These are important as part of the landscape, but I would not start here unless we confirm online item feeds.

### Style Labo Antiquites

- Likely relevant for Montreal discovery and brand presence.
- Current evidence is stronger for store-directory coverage than for a clean item catalog.
- Good candidate for:
  - manual inclusion
  - "featured shops" directory
  - later crawl review

### Trianon Boutique

- Montreal antique and MCM mix.
- Strong store presence, but less evidence of a clean resale item feed suitable for launch.
- Current decision:
  - defer
  - the emphasis appears too weighted toward French antiques / 18th-century decorative arts for the
    current MCM-first product

### Eco-Depot Montreal

- Strong local relevance.
- Better as a local shopping guide or manual source unless they expose consistent online inventory pages.
- Current decision:
  - defer for now despite local relevance
  - inventory is broad enough that adding it too early could weaken the focused curated feel

### Antiquites Van Horne

- Local Montreal antique shop with broad inventory and strong discovery value.
- Current evidence suggests it is a wide antiques source rather than a focused MCM furniture feed.
- Good candidate for:
  - local guide coverage
  - manual sourcing
  - later catalog review if stable online inventory appears

### Bien Beau

- Montreal-based vintage home decor shop with an e-commerce site and Quebec shipping messaging.
- Current evidence leans more toward decor and smaller objects than core furniture.
- Good candidate for:
  - decor expansion later
  - manual review if the project expands beyond furniture

## Crawl Strategy

### Phase 1: Direct-Shop Inventory Only

Already active:

1. Morceau
2. Showroom Montreal
3. Montreal Moderne
4. Le Centerpiece

Why:

- they already expose item pages
- they already show price on-page
- they clearly align with MCM / vintage furniture
- they have strong Canadian or Montreal shipping signals

### Phase 2: Local-First Expansion

Added:

1. Maison Singulier
2. Yardsale Vintage
3. BOND Vintage
4. Chez Lamothe

Why:

- strongest fit with the Montreal-first thesis
- similar local curation caliber to the current four active sources
- local pickup or local delivery is enough for these Montreal/agglomeration shops
- Maison Singulier, Yardsale Vintage, BOND Vintage, and Chez Lamothe now have local automated
  ingestion paths
- Chez Lamothe should be monitored for Square frontend API path/cache-version changes

### Phase 3: Regional Road-Trip Direct Shops

Add or spike next:

1. Habitat Mobilier
2. Green Wall Vintage
3. Mostly Danish

Why:

- expands beyond the Montreal agglomeration without becoming a generic Canadian marketplace
- keeps sources within shipping range or an easy 2-3 hour pickup from Montreal
- Habitat, Green Wall Vintage, and Mostly Danish look most likely to have automated item ingestion
- Deja Vu Meubles, Cornwall's Little Market, and A Fine Thing look source-relevant but should wait
  because they do not currently expose enough reliable item-level details, prices, and descriptions
  for ingestion on par with the existing shops

### Phase 4: Broader Canadian Direct Shops Or Marketplaces

Consider later:

1. Vintage Home Boutique
2. Urbano Vintej
3. 1stDibs
4. Chairish
5. Pamono

Why:

- larger inventory upside
- likely more duplication
- likely more crawl complexity
- probably better once the regional direct-shop model is stable

## Where The Data Likely Lives

For many of the strongest sources above, the pattern looks very close to Shopify-style ecommerce structure:

- `/products/...` item pages
- `/collections/...` category pages
- visible prices on listing cards
- visible main image on listing cards and product pages

That usually means the easiest starting points are:

1. collection pages for discovery
2. product pages for clean item data
3. sitemap files for full inventory coverage
4. embedded structured data or page JSON for normalized price/image/title extraction

Even before coding, this is the key strategic point:

- direct-shop ecommerce sources are much better launch candidates than trying to begin with marketplaces or Instagram-first stores

## Filtering Rules For Inclusion

An item should only appear on the site if:

1. it is clearly furniture or furniture-adjacent enough for the product vision
2. it is clearly resale, vintage, antique, restored, or one-of-a-kind
3. it has a public listing page
4. it has a visible image
5. it has a visible price
6. the source can reasonably sell to Montreal

For shipping, use this rule:

- include if the shop is in Montreal or the Montreal agglomeration and offers local pickup or local
  delivery
- include non-local shops only if they ship across Canada, ship to Canada, or offer worldwide
  shipping
- exclude if the source appears pickup-only outside Montreal and does not mention delivery or shipping
- revisit these rules if the product expands beyond the Montreal agglomeration or sees meaningful
  demand from users outside Montreal

## Likely Data Quality Problems

- sold items may stay online
- some shops mix decor and furniture in the same feed
- some shops require shipping quotes for oversized items
- some marketplaces include both vintage and new-made items
- some item pages may show "sold out" but still be indexable
- image quality and number of photos will vary a lot

This suggests the site should probably store:

- a normalized availability field
- a normalized source type (`direct_shop`, `marketplace`, `local_manual`)
- a confidence flag for `ships_to_montreal`

## Important Open Questions

These are the first things to resolve before implementation:

1. Do we want only authentic resale / vintage pieces, or also new MCM-style reproductions?
2. Do we want to show sold items for inspiration / archive, or only currently available listings?
3. Do we want only shops with self-serve checkout to Montreal, or also quote-based shipping?
4. Do we want to include decor and lighting, or furniture only?

My recommendation:

- focus on furniture only
- available items only
- allow quote-based shipping if the shop clearly serves Montreal or Canada
- exclude new reproduction-only shops from the main inventory

## Initial Source List

Priority 1:

- https://www.morceau.ca/
- https://www.showroommtl.com/
- https://www.montrealmoderne.com/
- https://www.greenwallvintage.ca/
- https://vintagehomeboutique.ca/
- https://lecenterpiece.com/

Priority 2:

- https://www.urbanovintej.ca/
- https://www.bananalab.ca/
- https://maisonsingulier.com/

Priority 3:

- https://www.1stdibs.com/
- https://www.chairish.com/
- https://www.pamono.ca/

Manual / later review:

- https://www.chezlamothe.com/
- https://www.stylelabo.com/ if active and cataloged online
- https://www.trianon-boutique.com/en/
- https://ecodepotmontreal.com/
- https://www.antiquitesvanhorne.com/ if stable inventory is exposed
- https://bienbeau.ca/

## Source Notes

Research used current public web pages checked on 2026-04-26, including:

- Morceau homepage and vintage collection
- Showroom Montreal homepage, about page, and nouveautes page
- Montreal Moderne homepage and nouveautes page
- Maison Singulier about page, collections page, and product pages
- Chez Lamothe domain plus supporting directory/writeup references
- Green Wall Vintage homepage, Montreal page, and delivery page
- Vintage Home Boutique about page and product pages
- Le Centerpiece homepage, about page, and shipping policy pages
- Urbano Vintej homepage
- Banana Lab shipping page
- 1stDibs Canada and shipping support pages
- Chairish shipping help pages
- Pamono homepage and about page

## Marketplace Overlap Check

Checked on: 2026-04-26

Platforms checked:

- 1stDibs
- Chairish
- Pamono
- Etsy
- eBay

Not yet checked:

- Facebook Marketplace

Follow-up: recheck Facebook Marketplace explicitly for the same shops. Public search may miss listings because Facebook Marketplace is location-scoped, login-sensitive, and sellers may use personal or alternate account names rather than shop brands.

Shops checked:

- Morceau
- Showroom Montreal
- Montreal Moderne
- Chez Lamothe
- Maison Singulier
- Le Centerpiece
- Trianon Boutique
- Style Labo Antiquites

Interpretation:

- `Confirmed` means I found clear public evidence that the shop is present on that marketplace under its own brand name.
- `No clear evidence found` means I did not find a convincing branded match in public search results.
- This is a practical research pass, not a legal or exhaustive proof of absence. Some shops may use alternate seller names.

| Shop | 1stDibs | Chairish | Pamono | Etsy | eBay | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Morceau | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | Direct site still appears primary |
| Showroom Montreal | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | Good sign for direct-source differentiation |
| Montreal Moderne | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | Good sign for direct-source differentiation |
| Chez Lamothe | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | Direct site inventory is crawlable through the Square storefront API, including prices and out-of-stock badges |
| Maison Singulier | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | Appears to rely on own site |
| Le Centerpiece | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | Appears to rely on own site |
| Trianon Boutique | Confirmed | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | Site itself links to 1stDibs |
| Style Labo Antiquites | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | Still looks more like local discovery than marketplace syndication |

Main takeaway:

- The only clear branded overlap I confirmed in this pass is `Trianon Boutique` on `1stDibs`.
- For the other local shops checked, I did not find clear evidence of branded presence on `1stDibs`, `Chairish`, `Pamono`, `Etsy`, or `eBay`.
- This pass did not cover `Facebook Marketplace`; treat Facebook Marketplace overlap as unresolved until a logged-in/location-aware manual check is done.
- That strengthens the case that a Montreal-focused direct-source aggregator could still add real value.

## Bottom Line

If the goal is to launch quickly with useful Montreal-relevant inventory, the best starting move is:

1. spider direct-shop ecommerce sites first
2. start with Montreal and Canada-friendly shops
3. delay large marketplaces until the item model and deduping rules are proven

Original launch sources:

1. Morceau
2. Showroom Montreal
3. Montreal Moderne
4. Le Centerpiece

Recently added local-first sources:

1. Maison Singulier
2. Yardsale Vintage
3. BOND Vintage
4. Chez Lamothe

## Showroom Montreal French Parser Evidence

Checked on: 2026-05-07

- Showroom Montreal listing `1912` stored source text: `Chaises en teck '60s Arne Hovmand-Olsen pour Onsild Møbelfabrik , Denmark restaurées 3500 $ / 6`.
- Prior extractors missed material and designer/maker because they leaned English-first: materials recognized `teak` but not `teck`, and designer/maker recognized `by ... for ...` but not French `... pour ...`.
- Category and condition worked because category mapping already included `chaises`, and condition matched `restaur`.
- Dimensions remain unavailable for this item because the source text does not include measurements.
- After switching extractor priority to French-first with English fallback and rerunning refresh, listing `1912` parsed as designer `Arne Hovmand-Olsen`, maker `Onsild Møbelfabrik`, material `teak`, condition `Restored`.

## Showroom Montreal Identity And Removal Behavior

Checked on: 2026-05-07

- Showroom Montreal source keys are built as `showroom:{item_id}` from Wix gallery item ids.
- Live Showroom parser source URLs point to the source page where the item was found, such as `https://www.showroommtl.com/nouveaute`, because the site does not expose stable item detail pages for every gallery item.
- Legacy fallback/override data may still contain older Wix `lightbox` URLs for seeded items; clean those up when refreshing fallback fixtures.
- Refresh upserts by `(source_shop_id, source_listing_key)`, so a stable Wix gallery item id preserves the same local listing row and `first_seen_at`.
- If a same-key item remains in the gallery and source text includes `vendu`, refresh sets `availability_status = sold_out`.
- If a previously seen source key disappears from a later authoritative refresh, refresh now sets `is_active = 0`, `availability_status = removed`, and updates `last_checked_at`; public detail URLs for inactive or removed listings return 404.
- If a source fetch or parser fails and fallback data is returned for a shop that already has listing records, refresh records a warning but does not treat the fallback set as authoritative and does not deactivate existing inventory.
- App-facing item numbers are deterministic from the preserved listing row id, e.g. listing `1912` renders as `MCM-001912`.
- Source-key drift reconciliation now checks same-shop exact normalized title first, then requires a high-confidence same image or same source description match before updating the existing row with the new source key.
- Ambiguous high-confidence matches are not merged; they are recorded in internal SQLite table `listing_identity_reviews` for later inspection outside the user-facing UI.
- Showroom can publish the same object on `nouveaute` and on category pages with different Wix
  `dataItem-*` lightbox ids.
- Confirmed duplicate examples in production on 2026-05-14: `MCM-006827` / `MCM-000955` and
  `MCM-007330` / `MCM-006849`.
- The parser now merges Showroom rows with the same normalized title, primary image, and source
  description before database upsert, preferring category-page source URLs over `nouveaute` URLs.
- Live parser check after the merge returned zero duplicate Showroom identity groups.

## Current UI And Localization Notes

Checked on: 2026-05-08

- User-facing prices are displayed from parsed `price_value` and active UI language, not the raw source price text.
- Prices display as whole-dollar CAD in both English and French.
- Listing cards currently omit repeated Montreal location and availability badges, show first-seen dates, and use localized quote-required fallbacks.
- Listing card item names, detail page item titles, and the `Montreal MCM` wordmark currently use the default sans-serif stack while the display-font direction is reconsidered.
- The header navigation is intended to align in the top header row with the wordmark, with the tagline below it.
- Raw source fields remain important for research and admin review: titles, source notes, unusual price text, dimensions, designer/maker text, and parser evidence should not be overwritten by display localization.

## Showroom Montreal Sold Archive Behavior

Checked on: 2026-05-14

- Showroom Montreal catalogue pages include many historical sold items. Their Wix gallery item title or description may contain `VENDU SOLD`, `vendu`, `vendue`, or `vendues`.
- The live parser now treats any normalized `vendu` marker in the Wix item title, parsed title, or description as `availability_status = sold_out`.
- Example: local listing `MCM-006538` has source key `showroom:dataItem-j1sgitoe2`. The live source shows `VENDU SOLD`; the parser now returns title `TINGSTROMS, série Casino SWEDEN`, source URL `https://www.showroommtl.com/tables-dappoints?lightbox=dataItem-j1sgitoe2`, and `availability_status = sold_out`.
- Showroom full refresh must not be capped at 240 items. On 2026-05-14, the uncapped live parse returned 4,029 unique Wix gallery items: 236 available and 3,793 sold out.
- Production default listing count after the authoritative Showroom refresh was 381 available listings across active shops, but importing the sold archive as active public records produced an implausible sold-out catalogue.
- Refresh policy should skip newly discovered records that are already `sold_out`; existing listings that were previously tracked should still update to `sold_out` when they sell.
- Public sold-out listings now require status history evidence of an `available` to `sold_out` transition, unless an explicit manual override marks the row sold out.
- This means a shop with a large sold archive, such as Showroom Montreal, will show zero public sold-out items until a listing Montreal MCM previously tracked as available later appears as sold.

## Habitat Mobilier French Parser Evidence

Checked on: 2026-05-30

- Listing `MCM-012122` source description from Habitat Mobilier includes French labeled measurements:
  `Largeur : 20” Profondeur : 16” Hauteur : 24”`.
- The previous dimensions extractor only handled compact `L x P x H` / `W x D x H` patterns and missed these labeled French dimensions.
- The same source description includes `Années 60`; the previous era extractor missed that French decade phrasing.
- The parser now extracts dimensions as `20”L x 16”P x 24”H` and era as `1960s` from that text.
- A deployed D1 audit found additional active listings with parseable dimensions in source descriptions:
  Morceau single-axis and parenthetical `D x H` patterns, Chez Lamothe `Ø x H/P` patterns,
  Mostly Danish centimetre and `H/W/D` shorthand patterns, Green Wall Vintage single-height
  captions, and a few Le Centerpiece small-object dimensions.
- Production D1 was backfilled for 310 active listings using the improved parser:
  306 broad source-specific dimension fills plus 4 Habitat multi-range / multi-piece fills.
- After the backfill, the deployed active listings scan returned zero rows where the current
  parser could recover dimensions from an empty `dimensions_text`.
