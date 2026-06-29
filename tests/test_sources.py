from __future__ import annotations

# ruff: noqa: F403,F405,I001

from tests.support import *


class SourceTests(AppTestCase):
    def test_worker_refresh_source_config_matches_python_sources(self) -> None:
        worker_source = (PROJECT_ROOT / "src" / "worker.js").read_text()
        source_slugs_match = re.search(
            r"const SOURCE_SLUGS = \[(?P<body>.*?)\];",
            worker_source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(source_slugs_match)
        assert source_slugs_match is not None
        worker_source_slugs = re.findall(r'"([^"]+)"', source_slugs_match.group("body"))
        python_source_slugs = [source.slug for source in SOURCE_DEFINITIONS]
        self.assertEqual(python_source_slugs, worker_source_slugs)

        worker_chunk_source_slugs = {
            match.group("name"): match.group("slug")
            for match in re.finditer(
                r'const (?P<name>[A-Z_]+)_SOURCE_SLUG = "(?P<slug>[^"]+)";',
                worker_source,
            )
        }
        worker_chunk_counts = {}
        for match in re.finditer(
            r"const (?P<name>[A-Z_]+)_CHUNK_COUNT = (?P<count>\d+);",
            worker_source,
        ):
            source_slug = worker_chunk_source_slugs[match.group("name")]
            worker_chunk_counts[source_slug] = int(match.group("count"))
        expected_chunk_counts = {
            **RECONCILABLE_CHUNK_COUNTS,
            "mostly-danish": 30,
        }
        self.assertEqual(expected_chunk_counts, worker_chunk_counts)

    def test_seed_materials_use_localized_material_tokens(self) -> None:
        seed_materials = {
            material.strip().lower()
            for listings in SEED_LISTINGS.values()
            for listing in listings
            for material in listing["materials"].split(",")
            if material.strip()
        }

        self.assertTrue(seed_materials)
        self.assertEqual(set(), seed_materials - set(MATERIAL_LABELS))

    def test_extractors_prefer_french_source_patterns(self) -> None:
        description = (
            "Chaises en teck '60s Arne Hovmand-Olsen pour Onsild Møbelfabrik, "
            "Denmark restaurées 3500 $ / 6"
        )
        self.assertEqual(
            _extract_designer_and_maker("Chaises en teck", description),
            ("Arne Hovmand-Olsen", "Onsild Møbelfabrik"),
        )
        self.assertEqual(_extract_materials(description), "teak")
        self.assertEqual(_extract_condition(description), "Restored")

    def test_extractors_keep_english_by_title_out_of_source_notes(self) -> None:
        description = (
            "Designed by Alessandro Gnocchi, Tiki Parete is based on an "
            "op-art triangular shape. View our store policies for more "
            "information prior to checkout."
        )
        self.assertEqual(
            _extract_designer_and_maker("Tiki Parete by Alessandro Gnocchi", description),
            ("Alessandro Gnocchi", ""),
        )

    def test_extractors_parse_english_by_for_title(self) -> None:
        self.assertEqual(
            _extract_designer_and_maker(
                "Anfibio Folding Sofa Bed by Alessandro Becchi for Giovannetti",
                "Italian convertible sofa bed.",
            ),
            ("Alessandro Becchi", "Giovannetti"),
        )

    def test_extractors_reject_contact_delivery_fragments_as_maker(self) -> None:
        self.assertEqual(
            _extract_designer_and_maker(
                "Dining Chairs",
                "Ottawa. Contactez-nous les détails - des frais s’appliques",
            ),
            ("", ""),
        )

    def test_morceau_source_only_uses_vintage_collection(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "morceau")
        self.assertEqual(source.listing_urls, ("https://www.morceau.ca/collections/vintage",))

    def test_showroom_gallery_items_use_lightbox_url(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        gallery_item = {
            "id": "dataItem-test",
            "uri": "fc24cc_test~mv2.jpg",
            "description": "Chaises en teck '60s\nArne Hovmand-Olsen\n3500 $ / 6",
        }
        with (
            patch("mcm.sources._fetch_html", return_value="<html></html>"),
            patch(
                "mcm.sources._extract_showroom_siteassets_url",
                return_value="https://example.com/assets",
            ),
            patch("mcm.sources._extract_showroom_gallery_items", return_value=[gallery_item]),
        ):
            listings = _extract_showroom_gallery_listings(
                source,
                "https://www.showroommtl.com/nouveaute",
            )

        self.assertEqual(
            listings[0]["source_listing_url"],
            "https://www.showroommtl.com/nouveaute?lightbox=dataItem-test",
        )

    def test_shopify_collection_product_uses_variant_availability(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "morceau")
        listing = _parse_shopify_collection_product(
            source,
            {
                "title": "Large teak mirror",
                "handle": "large-teak-mirror",
                "body_html": (
                    "<p>Large teak frame, 1960s.</p>"
                    "<p><span>MATERIALS</span><br>Teak and mirror</p>"
                    '<p><span>DIMENSIONS</span><br>31"W x 42"H</p>'
                ),
                "variants": [{"available": True, "price": "500.00"}],
                "images": [{"src": "https://cdn.shopify.com/image.jpg"}],
            },
        )

        self.assertEqual(
            listing["source_listing_url"],
            "https://www.morceau.ca/products/large-teak-mirror",
        )
        self.assertEqual(listing["availability_status"], "available")
        self.assertEqual(listing["price_value"], 500)
        self.assertEqual(listing["materials"], "Teak and mirror")
        self.assertEqual(listing["dimensions_text"], '31"W x 42"H')

    def test_shopify_collection_entry_can_skip_sold_out_products(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "le-centerpiece")
        products = [
            {
                "title": "Available Chair",
                "handle": "available-chair",
                "body_html": "<p>Vintage chair.</p>",
                "variants": [{"available": True, "price": "500.00"}],
            },
            {
                "title": "Sold Chair",
                "handle": "sold-chair",
                "body_html": "<p>Vintage chair.</p>",
                "variants": [{"available": False, "price": "400.00"}],
            },
        ]
        with patch("mcm.sources._fetch_shopify_collection_products", return_value=products):
            listings = _fetch_shopify_collection_entry(
                source,
                "https://lecenterpiece.com/collections/chairs",
                include_sold_out=False,
            )

        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0]["title"], "Available Chair")
        self.assertEqual(listings[0]["availability_status"], "available")

    def test_cargo_gallery_page_parses_yardsale_listing(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "yardsale-vintage")
        listing = _parse_cargo_page(
            source,
            {
                "id": "T1320580650",
                "title": "Jean Gillon Copa Sofa in Jacaranda Rosewood - 3800$",
                "purl": "jean-gillon-copa-sofa-3800",
                "content": (
                    "<p>Jean Gillon two seater sofa in Jacaranda Rosewood.</p>"
                    "<p>Dimensions: 58”W x 34”D x 32”H</p>"
                ),
                "thumbnail": {
                    "hash": "H2812705775408123180166743959247",
                    "name": "sofa.jpeg",
                },
            },
        )

        self.assertEqual(listing["source_listing_key"], "yardsale-vintage:T1320580650")
        self.assertEqual(listing["price_value"], 3800)
        self.assertEqual(listing["category"], "sofas")
        self.assertTrue(listing["primary_image_url"].startswith("https://freight.cargo.site/"))

    def test_square_product_page_parses_chez_lamothe_metadata(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "chez-lamothe")
        listing = _parse_square_product_page(
            source,
            "https://www.chezlamothe.com/product/buffet-en-teck/2950",
            """
                <html>
                  <head>
                    <meta property="og:title"
                          content="Buffet en teck par Johannes Andersen | Chez Lamothe">
                    <meta property="og:description"
                          content="Buffet en teck, Danemark circa 60. 72&#34;W x 18&#34;D x 31&#34;H. Livraison possible à Montréal.">
                    <meta property="og:image"
                          content="https://131647755.cdn6.editmysite.com/uploads/buffet.jpeg">
                  </head>
                </html>
                """,
        )

        self.assertEqual(listing["title"], "Buffet en teck par Johannes Andersen")
        self.assertEqual(listing["price_value"], None)
        self.assertEqual(listing["availability_status"], "available")
        self.assertEqual(listing["category"], "sideboards / credenzas")
        self.assertEqual(listing["materials"], "teak")

    def test_square_product_page_marks_chez_lamothe_sold_out_markers(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "chez-lamothe")
        listing = _parse_square_product_page(
            source,
            "https://www.chezlamothe.com/product/meuble-audio/123",
            """
                <html>
                  <head>
                    <meta property="og:title" content="Meuble audio extensible en teck">
                    <meta property="og:description" content="Rupture de stock">
                    <meta property="og:image"
                          content="https://131647755.cdn6.editmysite.com/uploads/meuble.jpeg">
                  </head>
                  <body>Article non disponible</body>
                </html>
                """,
        )

        self.assertEqual(listing["availability_status"], "sold_out")
        self.assertTrue(_square_product_is_sold_out("En rupture de stock", ""))

    def test_square_storefront_product_parses_chez_lamothe_price_and_stock(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "chez-lamothe")
        listing = _parse_square_storefront_product(
            source,
            {
                "id": "QAGXILITRN353YX2KW4PAOLS",
                "site_product_id": "QAGXILITRN353YX2KW4PAOLS",
                "name": "Système stéréo Clairtone en bois de rose modèle Project G2 T10",
                "short_description": "<p>Console en bois de rose. 78.5&quot;L x 14.75&quot;P x 27&quot;H</p>",
                "absolute_site_link": (
                    "https://www.chezlamothe.com/product/systeme-stereo/QAGXILITRN353YX2KW4PAOLS"
                ),
                "badges": {"out_of_stock": False},
                "inventory": {"all_variations_sold_out": False},
                "price": {"low": 18995, "low_subunits": 1899500},
                "images": {
                    "data": [
                        {
                            "absolute_urls": {
                                "1280": (
                                    "https://131647755.cdn6.editmysite.com/uploads/"
                                    "QAGXILITRN353YX2KW4PAOLS.jpeg?width=1280"
                                )
                            }
                        }
                    ]
                },
            },
        )

        self.assertEqual(listing["source_listing_key"], "chez-lamothe:QAGXILITRN353YX2KW4PAOLS")
        self.assertEqual(listing["price_value"], 18995)
        self.assertEqual(listing["price_raw"], "$18,995.00 CAD")
        self.assertEqual(listing["availability_status"], "available")
        self.assertIn("wood", listing["materials"])

    def test_squarespace_store_item_parses_habitat_listing(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "habitat-mobilier")
        listing = _parse_squarespace_store_item(
            source,
            {
                "id": "habitat-test",
                "title": "Buffet en teck",
                "fullUrl": "/boutique/p/buffet-teck",
                "excerpt": (
                    "<p>Punch Design. Canada. Années 60.</p>"
                    "<p>Entièrement en teck. Largeur : 72” Profondeur : 18”</p>"
                ),
                "assetUrl": "https://images.squarespace-cdn.com/buffet.jpg",
                "items": [
                    {"assetUrl": "https://images.squarespace-cdn.com/buffet-gallery.jpg"},
                    {"assetUrl": "https://images.squarespace-cdn.com/buffet-detail.jpg"},
                ],
                "variants": [
                    {
                        "qtyInStock": 1,
                        "priceMoney": {"currency": "CAD", "value": "1675.00"},
                    }
                ],
            },
        )

        self.assertEqual(listing["source_listing_key"], "habitat-mobilier:habitat-test")
        self.assertEqual(
            listing["source_listing_url"], "https://habitatmobilier.com/boutique/p/buffet-teck"
        )
        self.assertEqual(listing["price_value"], 1675)
        self.assertEqual(listing["availability_status"], "available")
        self.assertEqual(listing["materials"], "teak")
        self.assertEqual(
            listing["primary_image_url"], "https://images.squarespace-cdn.com/buffet-gallery.jpg"
        )
        self.assertEqual(
            listing["additional_image_urls"],
            [
                "https://images.squarespace-cdn.com/buffet-detail.jpg",
                "https://images.squarespace-cdn.com/buffet.jpg",
            ],
        )

    def test_squarespace_store_item_prefers_gallery_images_over_placeholder_asset(
        self,
    ) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "habitat-mobilier")
        listing = _parse_squarespace_store_item(
            source,
            {
                "id": "habitat-bed",
                "title": "Lit queen en teck",
                "fullUrl": "/boutique/p/lit-queen-en-teck-annees-70-mobican",
                "excerpt": "<p>Lit en teck Mobican. Années 70.</p>",
                "assetUrl": (
                    "https://static1.squarespace.com/static/5dc59aa470fe636e786603db/"
                    "5dc59b223056b3048c0c3116/6a174d412fb5d01bb9ef1dcc/1779912256893/"
                ),
                "items": [
                    {
                        "assetUrl": (
                            "https://images.squarespace-cdn.com/content/v1/"
                            "5dc59aa470fe636e786603db/e330ce50-084c-4849-b7b7-bf24e1f95ee7/"
                            "lit_queen_teck_mobican.jpg"
                        )
                    }
                ],
                "variants": [
                    {
                        "qtyInStock": 1,
                        "priceMoney": {"currency": "CAD", "value": "895.00"},
                    }
                ],
            },
        )

        self.assertEqual(
            listing["primary_image_url"],
            (
                "https://images.squarespace-cdn.com/content/v1/"
                "5dc59aa470fe636e786603db/e330ce50-084c-4849-b7b7-bf24e1f95ee7/"
                "lit_queen_teck_mobican.jpg"
            ),
        )

    def test_squarespace_store_item_skips_out_of_stock_habitat_items(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "habitat-mobilier")
        with self.assertRaises(ValueError):
            _parse_squarespace_store_item(
                source,
                {
                    "id": "habitat-sold",
                    "title": "Fauteuil en teck",
                    "fullUrl": "/boutique/p/fauteuil-teck",
                    "excerpt": "<p>Fauteuil en teck.</p>",
                    "assetUrl": "https://images.squarespace-cdn.com/fauteuil.jpg",
                    "variants": [{"qtyInStock": 0, "priceMoney": {"value": "695.00"}}],
                },
            )

    def test_shopify_collection_product_skips_gift_cards(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "morceau")
        with self.assertRaises(ValueError):
            _parse_shopify_collection_product(
                source,
                {
                    "title": "Gift Card",
                    "handle": "gift-card",
                    "variants": [{"available": True, "price": "100.00"}],
                },
            )

    def test_shopify_collection_product_skips_current_production(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "morceau")
        with self.assertRaises(ValueError):
            _parse_shopify_collection_product(
                source,
                {
                    "title": "Tiki Terra by Alessandro Gnocchi",
                    "handle": "tiki-terra-by-alessandro-gnocchi",
                    "body_html": "<p>Made in Italy, current production, on order.</p>",
                    "variants": [{"available": True, "price": "525.00"}],
                },
            )

    def test_shopify_collection_products_walk_pages_until_empty(self) -> None:
        payloads = [
            json.dumps({"products": [{"handle": "one"}]}),
            json.dumps({"products": [{"handle": "two"}]}),
            json.dumps({"products": []}),
        ]
        with patch("mcm.sources._fetch_html", side_effect=payloads):
            products = _fetch_shopify_collection_products(
                "https://www.morceau.ca/collections/furniture"
            )

        self.assertEqual([product["handle"] for product in products], ["one", "two"])

    def test_showroom_gallery_skips_generated_dataitem_titles(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        gallery_items = [
            {"id": "dataItem-header1", "uri": "fc24cc_header1~mv2.jpg", "title": ""},
            {"id": "dataItem-header2", "uri": "fc24cc_header2~mv2.jpg", "title": ""},
            {
                "id": "dataItem-placeholder",
                "uri": "fc24cc_placeholder~mv2.jpg",
                "description": "Contactez nous pour les détails",
            },
            {
                "id": "dataItem-real",
                "uri": "fc24cc_real~mv2.jpg",
                "description": "Chaises en teck '60s\n1200 $ / 4",
            },
        ]
        with (
            patch("mcm.sources._fetch_html", return_value="<html></html>"),
            patch(
                "mcm.sources._extract_showroom_siteassets_url",
                return_value="https://example.com/assets",
            ),
            patch("mcm.sources._extract_showroom_gallery_items", return_value=gallery_items),
        ):
            listings = _extract_showroom_gallery_listings(
                source,
                "https://www.showroommtl.com/nouveaute",
            )

        self.assertEqual(len(listings), 1)
        self.assertEqual(
            listings[0]["source_listing_key"],
            _showroom_source_listing_key(
                "Chaises en teck '60s",
                "https://static.wixstatic.com/media/fc24cc_real~mv2.jpg",
                "Chaises en teck '60s 1200 $ / 4",
            ),
        )

    def test_showroom_french_dimensions_and_era_are_extracted(self) -> None:
        text = (
            "Fauteuils en teck '60s Arne Hovmand Olsen pour P Mikkelsen, Denmark "
            "restaurés, nouveau recouvrement 26''L x 30''P x 29.5''H assise 15'' H "
            "3250 $ / paire"
        )

        self.assertEqual(_extract_era(text), "1960s")
        self.assertEqual(_extract_dimensions(text), "26''L x 30''P x 29.5''H")

    def test_habitat_french_labeled_dimensions_and_era_are_extracted(self) -> None:
        text = (
            "Merton Gershun pour American of Martinsville. États-Unis. Années 60. "
            "En paire. En noyer avec insertions et poignées en aluminium. "
            "Excellente condition. Complètement restaurées avec nouveau fini durable. "
            "Largeur : 20” Profondeur : 16” Hauteur : 24” - Livraison possible partout au Québec."
        )

        self.assertEqual(_extract_era(text), "1960s")
        self.assertEqual(_extract_dimensions(text), "20”L x 16”P x 24”H")

    def test_habitat_french_range_dimensions_are_extracted(self) -> None:
        text = (
            "REFF. Canada. Années 60. Entièrement en bois de rose. "
            "Largeur : 125” Profondeur : 16” Hauteur : 88” à 100” (rails)"
        )

        self.assertEqual(_extract_dimensions(text), "125”L x 16”P x 88”/100”H")

    def test_habitat_prefixed_multi_piece_dimensions_are_extracted(self) -> None:
        text = (
            "Fauteuil: Largeur : 32” Profondeur : 35” Hauteur (assise) : 17” "
            "Hauteur totale : 38” Ottoman: Largeur : 21” Profondeur : 18” Hauteur : 14”"
        )

        self.assertEqual(
            _extract_dimensions(text),
            "Fauteuil: 32”L x 35”P x 38”H; Ottoman: 21”L x 18”P x 14”H",
        )

    def test_chez_lamothe_diameter_dimensions_are_extracted(self) -> None:
        text = (
            "Lampe champignon Space Age en verre blanc et orangé attribuées à Pukeberg, "
            'Suède circa 60 - en parfaite condition d\'origine 8,5"Ø x 9"H '
            "Expédition possible au Canada"
        )

        self.assertEqual(_extract_dimensions(text), '8,5"Ø x 9"H')

    def test_chez_lamothe_diameter_depth_dimensions_are_extracted(self) -> None:
        text = (
            "Petit miroir mid century en acier et laiton, circa 60 - excellente condition "
            'd\'origine 12"Ø x 2,75"P Expédition possible au Canada'
        )

        self.assertEqual(_extract_dimensions(text), '12"Ø x 2,75"P')

    def test_parenthetical_dimension_notes_are_removed(self) -> None:
        text = (
            "Ceramic vase by Scheurich. Made in West Germany, 1980’s. "
            '5,5"D(with handle) x 11”H US/CAD shipping available at checkout.'
        )

        self.assertEqual(_extract_dimensions(text), '5,5"D x 11”H')

    def test_mostly_danish_centimetre_dimensions_are_extracted(self) -> None:
        text = (
            "ITEM# 4024267 MAHOGANY SOFA SET Sofa: Length 190 cm. "
            "Depth 80 cm. Height 77 cm excl. pad. Seat height 45 cm."
        )

        self.assertEqual(_extract_dimensions(text), "190cmL x 80cmD x 77cmH")

    def test_mostly_danish_shorthand_dimensions_are_extracted(self) -> None:
        text = 'Rosewood secretary designed by Ib Kofod-Larsen. H. 56.5" x W. 39.3" x D. 18.25"'

        self.assertEqual(_extract_dimensions(text), '56.5"H x 39.3"W x 18.25"D')

    def test_single_axis_dimensions_are_extracted(self) -> None:
        text = "Vintage EM77 stainless steel vacuum jug. Made in Denmark, 1970’s. 12”H"

        self.assertEqual(_extract_dimensions(text), "12”H")

    def test_seat_and_back_height_are_not_single_axis_dimensions(self) -> None:
        text = (
            "Poul Hundevad pour Vamdrup Stolefabrik. H (dossier) : 31” "
            "H (assise) : 18” Largeur : 19”"
        )

        self.assertEqual(_extract_dimensions(text), "")

    def test_curly_apostrophe_decade_is_extracted(self) -> None:
        text = (
            "Teak wine/ice bucket by Jens Quistgaard for Dansk. "
            'Made in Denmark, 1950’s. Restored. 7,5"D x 15”H'
        )

        self.assertEqual(_extract_era(text), "1950s")

    def test_showroom_gallery_skips_promotional_store_hours_cards(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        gallery_items = [
            {
                "id": "dataItem-promo",
                "uri": "fc24cc_promo~mv2.jpg",
                "description": "Joyeuses Pâques!\nOuvert samedi 19 avril 12h à 17h\nFermé dimanche 20 avril",
            },
            {
                "id": "dataItem-real",
                "uri": "fc24cc_real~mv2.jpg",
                "description": "Fauteuil en teck '60s\n1850 $",
            },
        ]
        with (
            patch("mcm.sources._fetch_html", return_value="<html></html>"),
            patch(
                "mcm.sources._extract_showroom_siteassets_url",
                return_value="https://example.com/assets",
            ),
            patch("mcm.sources._extract_showroom_gallery_items", return_value=gallery_items),
        ):
            listings = _extract_showroom_gallery_listings(
                source,
                "https://www.showroommtl.com/nouveaute",
            )

        self.assertEqual(len(listings), 1)
        self.assertEqual(
            listings[0]["source_listing_key"],
            _showroom_source_listing_key(
                "Fauteuil en teck '60s",
                "https://static.wixstatic.com/media/fc24cc_real~mv2.jpg",
                "Fauteuil en teck '60s 1850 $",
            ),
        )

    def test_showroom_gallery_marks_sold_items(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        gallery_items = [
            {
                "id": "dataItem-sold",
                "uri": "fc24cc_sold~mv2.jpg",
                "description": "Buffet en teck '60s\nVendu",
            },
            {
                "id": "dataItem-real",
                "uri": "fc24cc_real~mv2.jpg",
                "description": "Fauteuil en teck '60s\n1850 $",
            },
        ]
        with (
            patch("mcm.sources._fetch_html", return_value="<html></html>"),
            patch(
                "mcm.sources._extract_showroom_siteassets_url",
                return_value="https://example.com/assets",
            ),
            patch("mcm.sources._extract_showroom_gallery_items", return_value=gallery_items),
        ):
            listings = _extract_showroom_gallery_listings(
                source,
                "https://www.showroommtl.com/nouveaute",
            )

        self.assertEqual(len(listings), 2)
        self.assertEqual(
            listings[0]["source_listing_key"],
            _showroom_source_listing_key(
                "Buffet en teck '60s",
                "https://static.wixstatic.com/media/fc24cc_sold~mv2.jpg",
                "Buffet en teck '60s Vendu",
            ),
        )
        self.assertEqual(listings[0]["availability_status"], "sold_out")
        self.assertEqual(
            listings[1]["source_listing_key"],
            _showroom_source_listing_key(
                "Fauteuil en teck '60s",
                "https://static.wixstatic.com/media/fc24cc_real~mv2.jpg",
                "Fauteuil en teck '60s 1850 $",
            ),
        )
        self.assertEqual(listings[1]["availability_status"], "available")

    def test_showroom_gallery_marks_title_overlay_sold_items(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        gallery_items = [
            {
                "id": "dataItem-sold",
                "uri": "fc24cc_sold~mv2.jpg",
                "title": "VENDU SOLD",
                "description": "TINGSTROMS, série Casino\nSWEDEN",
            },
        ]
        with (
            patch("mcm.sources._fetch_html", return_value="<html></html>"),
            patch(
                "mcm.sources._extract_showroom_siteassets_url",
                return_value="https://example.com/assets",
            ),
            patch("mcm.sources._extract_showroom_gallery_items", return_value=gallery_items),
        ):
            listings = _extract_showroom_gallery_listings(
                source,
                "https://www.showroommtl.com/tables-dappoints",
            )

        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0]["title"], "TINGSTROMS, série Casino SWEDEN")
        self.assertEqual(listings[0]["availability_status"], "sold_out")

    def test_showroom_key_uses_description_before_image(self) -> None:
        title = "Lampes, suspensions en acier '60s Jo Hammerborg pour Fog & Morup, Denmark"
        description = (
            "Lampes, suspensions en acier '60s Jo Hammerborg pour Fog & Morup, Denmark "
            "modèle Corona (Cône) 9.5'' D x 18''H 1500 $ / l'ensemble"
        )

        first_key = _showroom_source_listing_key(
            title,
            "https://static.wixstatic.com/media/fc24cc_first~mv2.jpg",
            description,
        )
        second_key = _showroom_source_listing_key(
            title,
            "https://static.wixstatic.com/media/fc24cc_second~mv2.jpg",
            description.lower(),
        )

        self.assertEqual(first_key, second_key)

    def test_showroom_full_refresh_keeps_all_unique_gallery_items(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        showroom_listings = [
            {
                "source_listing_key": f"showroom:dataItem-{index}",
                "primary_image_url": f"https://static.wixstatic.com/media/item-{index}.jpg",
            }
            for index in range(241)
        ]

        with patch("mcm.sources._fetch_showroom_entry", return_value=showroom_listings):
            listings = _fetch_showroom(source)

        self.assertEqual(len(listings), 241)

    def test_showroom_full_refresh_merges_same_item_from_nouveaute_and_category(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal")
        duplicate_from_nouveaute = {
            "source_listing_url": "https://www.showroommtl.com/nouveaute?lightbox=dataItem-new",
            "source_listing_key": "showroom:dataItem-new",
            "title": "Commode en teck '60s REFF, Canada",
            "primary_image_url": "https://static.wixstatic.com/media/fc24cc_duplicate.jpg",
            "source_description": "Commode en teck '60s REFF, Canada restaurée 72'' L x 18.75'' P x 27'' H 1350 $",
        }
        duplicate_from_category = {
            **duplicate_from_nouveaute,
            "source_listing_url": "https://www.showroommtl.com/lits-commodes?lightbox=dataItem-category",
            "source_listing_key": "showroom:dataItem-category",
        }

        def fake_fetch_entry(_source: object, entry_url: str) -> list[dict[str, Any]]:
            if entry_url.endswith("/nouveaute"):
                return [duplicate_from_nouveaute]
            if entry_url.endswith("/lits-commodes"):
                return [duplicate_from_category]
            return []

        with patch("mcm.sources._fetch_showroom_entry", side_effect=fake_fetch_entry):
            listings = _fetch_showroom(source)

        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0]["source_listing_key"], "showroom:dataItem-category")
        self.assertIn("/lits-commodes?", listings[0]["source_listing_url"])

    def test_fetch_html_percent_encodes_non_ascii_url_parts(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args) -> None:
                return None

            def read(self) -> bytes:
                return b"ok"

        captured_url = ""

        def fake_urlopen(request, timeout):  # noqa: ANN001, ARG001
            nonlocal captured_url
            captured_url = request.full_url
            captured_url.encode("ascii")
            return FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            self.assertEqual(_fetch_html("https://example.com/assets?title=Knoll®"), "ok")

        self.assertEqual(captured_url, "https://example.com/assets?title=Knoll%C2%AE")

    def test_showroom_siteassets_url_preserves_registry_query_parameter(self) -> None:
        html = """
            <html>
              <script>window.firstPageId = 'abc';</script>
              <link id="features_abc" href="https://siteassets.parastorage.com/pages/pages/thunderbolt?x=1&registryLibrariesTopology=%5B%5D">
            </html>
            """

        self.assertEqual(
            _extract_showroom_siteassets_url(html),
            "https://siteassets.parastorage.com/pages/pages/thunderbolt?x=1&registryLibrariesTopology=%5B%5D",
        )

    def test_sources_module_public_api_is_explicit(self) -> None:
        self.assertEqual(
            set(sources_module.__all__),
            {
                "SOURCE_DEFINITIONS",
                "ParsedListing",
                "SourceDefinition",
                "fetch_chez_lamothe_page_listings",
                "fetch_le_centerpiece_entry_listings",
                "fetch_shopify_collection_page_listings",
                "fetch_showroom_entry_listings",
                "fetch_source_listings",
            },
        )
        self.assertNotIn("SECTION_LABELS", sources_module.__all__)
        self.assertTrue(hasattr(sources_module, "_SECTION_LABELS"))

    def test_fetch_source_listings_dispatches_by_parser(self) -> None:
        expected_listing = {"source_listing_url": "https://example.test/item"}
        dispatch_cases = [
            ("morceau", "_fetch_shopify_collection"),
            ("showroom-montreal", "_fetch_showroom"),
            ("montreal-moderne", "_fetch_montreal_moderne"),
            ("yardsale-vintage", "_fetch_cargo_gallery"),
            ("chez-lamothe", "_fetch_square_storefront"),
            ("habitat-mobilier", "_fetch_squarespace_store"),
        ]

        for slug, function_name in dispatch_cases:
            source = next(source for source in SOURCE_DEFINITIONS if source.slug == slug)
            with self.subTest(slug=slug):
                with patch(
                    f"mcm.sources.{function_name}", return_value=[expected_listing]
                ) as fetch:
                    listings, error = fetch_source_listings(source)

                fetch.assert_called_once_with(source)
                self.assertEqual(listings, [expected_listing])
                self.assertIsNone(error)

    def test_fetch_source_listings_returns_seed_fallback_on_parser_error(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "morceau")

        with patch("mcm.sources._fetch_shopify_collection", side_effect=ValueError("broken")):
            listings, error = fetch_source_listings(source)

        self.assertIn("broken", error or "")
        self.assertTrue(listings)
        self.assertEqual(listings[0]["parse_confidence"], 0.45)
        self.assertEqual(listings[0]["ingest_source_type"], "seed_fallback")

    def test_fetch_source_listings_unknown_parser_and_source_limits(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "morceau")
        unknown_source = replace(source, parser="unknown_parser")

        listings, error = fetch_source_listings(unknown_source)

        self.assertTrue(listings)
        self.assertIn("Unknown parser: unknown_parser", error or "")
        self.assertEqual(_source_listing_limit(source), 200)
        self.assertEqual(
            _source_listing_limit(
                next(source for source in SOURCE_DEFINITIONS if source.slug == "mostly-danish")
            ),
            600,
        )

    def test_chunk_source_dispatchers_validate_source_and_entry(self) -> None:
        showroom = next(
            source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal"
        )
        le_centerpiece = next(
            source for source in SOURCE_DEFINITIONS if source.slug == "le-centerpiece"
        )
        chez_lamothe = next(
            source for source in SOURCE_DEFINITIONS if source.slug == "chez-lamothe"
        )
        morceau = next(source for source in SOURCE_DEFINITIONS if source.slug == "morceau")
        expected_listing = {"source_listing_url": "https://example.test/item"}

        with patch("mcm.sources._fetch_showroom_entry", return_value=[expected_listing]) as fetch:
            listings, error = fetch_showroom_entry_listings(showroom, showroom.listing_urls[0])
        fetch.assert_called_once_with(showroom, showroom.listing_urls[0])
        self.assertEqual(listings, [expected_listing])
        self.assertIsNone(error)
        self.assertEqual(fetch_showroom_entry_listings(morceau, morceau.listing_urls[0])[0], [])
        self.assertIn(
            "Unknown Showroom listing URL",
            fetch_showroom_entry_listings(showroom, "https://example.test/missing")[1] or "",
        )

        with patch(
            "mcm.sources._fetch_shopify_collection_entry",
            return_value=[expected_listing],
        ) as fetch:
            listings, error = fetch_le_centerpiece_entry_listings(
                le_centerpiece, le_centerpiece.listing_urls[0]
            )
        fetch.assert_called_once_with(
            le_centerpiece, le_centerpiece.listing_urls[0], include_sold_out=False
        )
        self.assertEqual(listings, [expected_listing])
        self.assertIsNone(error)
        self.assertIn(
            "Le Centerpiece parser",
            fetch_le_centerpiece_entry_listings(morceau, morceau.listing_urls[0])[1] or "",
        )
        self.assertIn(
            "Unknown Le Centerpiece listing URL",
            fetch_le_centerpiece_entry_listings(le_centerpiece, "https://example.test/missing")[1]
            or "",
        )

        with patch(
            "mcm.sources._fetch_square_storefront_page", return_value=[expected_listing]
        ) as fetch:
            listings, error = fetch_chez_lamothe_page_listings(chez_lamothe, 1, per_page=5)
        fetch.assert_called_once_with(chez_lamothe, 1, per_page=5)
        self.assertEqual(listings, [expected_listing])
        self.assertIsNone(error)
        self.assertIn(
            "Chez Lamothe parser",
            fetch_chez_lamothe_page_listings(morceau, 1)[1] or "",
        )
        self.assertIn(
            "Unknown Chez Lamothe page",
            fetch_chez_lamothe_page_listings(chez_lamothe, 0)[1] or "",
        )

    def test_shopify_page_listing_dispatch_filters_bad_and_sold_products(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.slug == "morceau")
        entry_url = source.listing_urls[0]
        products = [{"handle": "available"}, {"handle": "bad"}, {"handle": "sold"}]

        def fake_parse(_source: object, product: dict[str, str]) -> dict[str, Any]:
            if product["handle"] == "bad":
                raise ValueError("bad product")
            return {
                "source_listing_url": f"https://example.test/{product['handle']}",
                "availability_status": "sold_out" if product["handle"] == "sold" else "available",
            }

        with (
            patch("mcm.sources._fetch_shopify_collection_products_page", return_value=products),
            patch("mcm.sources._parse_shopify_collection_product", side_effect=fake_parse),
        ):
            listings, error = fetch_shopify_collection_page_listings(
                source,
                entry_url,
                1,
                per_page=2,
                include_sold_out=False,
            )

        self.assertIsNone(error)
        self.assertEqual(
            listings,
            [
                {
                    "source_listing_url": "https://example.test/available",
                    "availability_status": "available",
                }
            ],
        )
        self.assertIn(
            "Shopify collection parser",
            fetch_shopify_collection_page_listings(
                next(source for source in SOURCE_DEFINITIONS if source.slug == "showroom-montreal"),
                entry_url,
                1,
            )[1]
            or "",
        )
        self.assertIn(
            "Unknown Shopify collection URL",
            fetch_shopify_collection_page_listings(source, "https://example.test/missing", 1)[1]
            or "",
        )
        self.assertIn(
            "Unknown Shopify collection page",
            fetch_shopify_collection_page_listings(source, entry_url, 0)[1] or "",
        )
