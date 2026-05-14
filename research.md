# Montreal MCM Resale Research

Date: 2026-04-26
Updated: 2026-05-14

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

This means the research priority is no longer just "what should we build first." It is now also "which researched sources should be added next, and in what order, after the existing MVP is stabilized."

## Recommendation

Start with a small set of stores that already have:

- public item detail pages
- clear prices on-page
- item photos on-page
- explicit Canada-wide, Montreal, or international shipping language

Best first spider targets:

1. Morceau Montreal
2. Showroom Montreal
3. Montreal Moderne
4. Green Wall Vintage
5. Vintage Home Boutique
6. Le Centerpiece

Best secondary expansion targets:

1. Urbano Vintej
2. Banana Lab
3. Maison Singulier
4. 1stDibs
5. Chairish
6. Pamono

Best manual / later-review targets:

1. Chez Lamothe
2. Style Labo Antiquites
3. Trianon Boutique
4. Eco-Depot Montreal
5. Antiquites Van Horne
6. Bien Beau

Reason: the first group appears to expose item pages and prices clearly, while the manual group looks stronger as store discovery than as clean item-feed sources.

## Recommended Next Source Order From Here

As of 2026-05-14, the next expansion should stay local-first. For Montreal and agglomeration-area
shops, local pickup or local delivery is enough; Canada-wide shipping is not required.

If the product later expands beyond the Montreal agglomeration, or if traffic materially shifts
toward users outside Montreal, shipping requirements should be revisited before adding more
non-local sources.

### Selected Local Expansion Set

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

Likely crawl candidates:

1. Maison Singulier
2. BOND Vintage

Likely manual/profile-first candidates:

1. Yardsale Vintage
2. Chez Lamothe

Reason:

- Maison Singulier has public collection/product pages, but needs clean live-vs-archive filtering.
- BOND Vintage appears to have Shopify collection/product pages with prices and sold states, but its
  active inventory may be sparse or mostly sold out.
- Yardsale Vintage has strong brand/source fit, but purchase appears contact-based and the catalog
  is not yet proven as a clean automated feed.
- Chez Lamothe is highly aligned locally, but current evidence still points more to social/manual
  sourcing than a stable public item feed.

### Explicitly Deferred

1. EcoDepot Montreal
2. Trianon Boutique
3. Green Wall Vintage
4. Vintage Home Boutique
5. Banana Lab
6. 1stDibs
7. Chairish
8. Pamono

Reason:

- EcoDepot is relevant locally, but inventory is broad and thrift-like enough that it could weaken
  focus unless added with careful category filtering.
- Trianon is high caliber, but the emphasis is French antiques / 18th-century decorative arts rather
  than the core MCM furniture product.
- Green Wall Vintage and Vintage Home Boutique remain useful Canada-friendly candidates, but they
  are not local enough for the next expansion step.
- Banana Lab should not be treated as Montreal-local based on the latest review.
- Large marketplaces remain a later strategy because they introduce duplication, crawl complexity,
  and weaker direct-source differentiation.

## Research Questions That Still Matter

The build has answered the "is this product worth prototyping?" question. The main research questions still worth validating are now:

1. Which active source parsers are stable enough to rely on without frequent seed fallback?
2. Can Maison Singulier and BOND Vintage be crawled cleanly without importing archive-only or sold
   inventory?
3. Can Yardsale Vintage and Chez Lamothe expose enough public listing data to graduate from
   manual/profile-first sources to automated sources?
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
  - this should be the first expansion source after the current four active shops
  - implementation must avoid importing archive-only inventory as available inventory

### Yardsale Vintage

- URL: https://yardsale-vintage.com/
- Why it matters: Montreal studio focused on restored, one-of-a-kind vintage furniture with a strong
  fit for the curated local thesis.
- Local signal:
  - about page says the studio operates in Montreal
  - pieces can be viewed in person by appointment
- Delivery signal:
  - FAQ/about pages say shipping is available across Canada and the United States by quote
  - for this project, local appointment/pickup or local delivery would be enough even without
    Canada-wide shipping
- Crawlability: medium to low until verified. Public site exists, but purchase appears
  contact-based and the item catalog is not yet proven as a clean feed.
- Notes:
  - good candidate for shop profile and manual-source support first
  - only promote to automated ingestion if current inventory pages expose title, image, price or
    quote status, and availability reliably

### BOND Vintage

- URL: https://bondvintage.com/
- Why it matters: Montreal shop selling vintage modern furniture and home accessories from multiple
  periods and countries.
- Local signal:
  - about page lists the shop on boulevard Saint-Laurent in Montreal
- Crawlability: medium to strong technically because it appears Shopify-based.
- Notes:
  - collection page shows product cards, prices, and sold-out states
  - concern: current visible inventory may be mostly sold out, so usefulness depends on active stock
    volume
  - good parser spike candidate after Maison Singulier

### Chez Lamothe

- URL: https://www.chezlamothe.com/
- Why it matters: local Montreal source for restored Mid-Century furniture, especially teak,
  Scandinavian, Danish, and Canadian pieces.
- Local signal:
  - third-party listings and writeups place it in Montreal and describe it as a restored MCM
    furniture shop
- Crawlability: low based on current evidence. The domain exists, but no stable public item feed has
  been verified.
- Notes:
  - high-caliber local source and should be part of the product
  - start as a shop profile / manual-source candidate
  - only add automated crawling if the site or another first-party channel exposes stable listings

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

## Montreal Shops Worth Tracking But Not Ideal First Spider Targets

These are important as part of the landscape, but I would not start here unless we confirm online item feeds.

### Chez Lamothe

- URL: https://www.chezlamothe.com/
- Why it matters: clearly a local Montreal mid-century shop focused on recovered and restored quality pieces.
- Local signal:
  - third-party directory coverage places it on Rue Saint-Hubert in Montreal
  - outside writeups describe it as a Montreal boutique for restored 1950s-1970s MCM furniture and decor
- Crawlability: low to medium based on current evidence. The domain is live, but I could not verify a clean public inventory feed from the site in this pass.
- Notes:
  - Important to include in the research set.
  - Better treated as a manual-review or social-first source unless the site exposes stable listing pages.

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

Add:

1. Maison Singulier
2. BOND Vintage
3. Yardsale Vintage
4. Chez Lamothe

Why:

- strongest fit with the Montreal-first thesis
- similar local curation caliber to the current four active sources
- local pickup or local delivery is enough for these Montreal/agglomeration shops
- Maison Singulier and BOND Vintage look most likely to support automated crawling
- Yardsale Vintage and Chez Lamothe may need manual/profile-first support

### Phase 3: Broader Canadian Direct Shops Or Marketplaces

Consider later:

1. Green Wall Vintage
2. Vintage Home Boutique
3. Urbano Vintej
4. 1stDibs
5. Chairish
6. Pamono

Why:

- large inventory upside
- likely more duplication
- likely more crawl complexity
- probably better once the core data model is stable

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
| Chez Lamothe | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | No clear evidence found | Lower-confidence shop overall because site inventory is harder to verify |
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

If I were choosing the exact first four sources, I would start with:

1. Morceau
2. Showroom Montreal
3. Montreal Moderne
4. Le Centerpiece

Very close next additions:

1. Maison Singulier
2. BOND Vintage
3. Yardsale Vintage
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
