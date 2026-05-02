# Montreal MCM Resale Research

Date: 2026-04-26
Updated: 2026-05-02

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
- lightweight email-based local session login
- freshness and availability labels
- bilingual English / French UI
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

Given the current implementation, the research-backed next source order should be:

### Near-Term Additions

1. Green Wall Vintage
2. Vintage Home Boutique
3. Maison Singulier

Reason:

- they fit the Montreal / Canada-friendly thesis
- they are the clearest gap between the original research and the current live source set
- they add meaningful inventory without forcing a marketplace-style expansion

### Next Expansion After That

1. Urbano Vintej
2. Banana Lab

Reason:

- both remain promising direct-source additions
- both appear worth doing after the first missing launch sources are live

### Still Defer For Later

1. 1stDibs
2. Chairish
3. Pamono

Reason:

- higher duplication risk
- higher crawl complexity
- better evaluated only after direct-shop ingestion, change tracking, and duplicate handling are stronger

## Research Questions That Still Matter

The build has answered the "is this product worth prototyping?" question. The main research questions still worth validating are now:

1. Which active source parsers are stable enough to rely on without frequent seed fallback?
2. Which missing direct-shop sources can be added with the least parser complexity?
3. How often do target sources expose sold, removed, or ambiguous inventory states?
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
  - this should be added to the research set, but I would still start after the simpler first-wave sources because inventory appears mixed between available, archive, and non-furniture items

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

### Eco-Depot Montreal

- Strong local relevance.
- Better as a local shopping guide or manual source unless they expose consistent online inventory pages.

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

Start with:

1. Morceau
2. Showroom Montreal
3. Montreal Moderne
4. Green Wall Vintage
5. Vintage Home Boutique
6. Le Centerpiece

Why:

- they already expose item pages
- they already show price on-page
- they clearly align with MCM / vintage furniture
- they have strong Canadian or Montreal shipping signals

### Phase 2: Broader Canadian Direct Shops

Add:

1. Urbano Vintej
2. Banana Lab
3. Maison Singulier

Why:

- useful incremental inventory
- slightly more validation needed on page consistency

### Phase 3: Marketplaces

Add:

1. 1stDibs
2. Chairish
3. Pamono

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

- include if the shop is in Montreal, ships across Canada, ships to Canada, or offers worldwide shipping
- exclude if the source appears pickup-only outside Montreal and does not mention delivery or shipping

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
4. Green Wall Vintage

Very close next additions:

1. Vintage Home Boutique
2. Le Centerpiece
