"""S152-09 — the BookingCatalogue CMS component, the twin of ``BookingCatalogue.vue``.

* facets from ``GET /api/v1/booking/filters`` and each ``options_endpoint``;
* resources from ``GET /api/v1/booking/resources`` with the SPA's query: ``page``,
  ``per_page`` 12, ``q``, ``tags`` comma-joined and every other query value as a
  facet (``type``, ``category``, ``availability_from`` / ``_to``) —
  ``useCatalogueFilters`` semantics; theme form fields never reach the API;
* a chip submits ``toggle_tag``, the view switch ``toggle_view``; pager buttons
  their ``page``, any other change starts again at page 1;
* cards: link, PriceDisplay ``net ?? price`` / ``gross ?? price`` in the app
  default currency (``GET /api/v1/config``, read once per render) + the unit
  without ``per_``, the spots line when capacity > 1, labelled tags.
"""
from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_booking.tests.unit.fakes import FakeBookingApi
from plugins.theme_booking.theme_booking.catalogue import BookingCatalogue
from plugins.theme_checkout.tests.unit.fakes import FakeCheckoutApi, FakeThemeRequest


def _catalogue(query=None, api=None, path="/booking", checkout_api=None):
    api = api or FakeBookingApi()
    checkout_api = checkout_api or FakeCheckoutApi()
    context = BookingCatalogue(api.factory, checkout_api.factory).build_context(
        {}, {}, {}, FakeThemeRequest(query or {}, path=path)
    )
    return context, api


def _resources_query(api):
    return api.called("resources")[0][1]


def test_the_default_query_is_page_one_twelve_per_page():
    context, api = _catalogue()

    assert _resources_query(api) == {"page": 1, "per_page": 12}
    assert context["state"] == "resources"
    assert context["form_action"] == "/booking"
    assert context["view_mode"] == "grid"


def test_search_tags_facets_and_page_reach_the_api():
    _context, api = _catalogue(
        {
            "q": "smith",
            "tags": "quiet,sunny",
            "type": "specialist",
            "category": "",
            "availability_from": "2026-11-02",
            "page": "2",
        }
    )

    assert _resources_query(api) == {
        "page": 2,
        "per_page": 12,
        "q": "smith",
        "tags": "quiet,sunny",
        "type": "specialist",
        "availability_from": "2026-11-02",
    }


def test_theme_form_fields_never_reach_the_api():
    _context, api = _catalogue(
        {"catalog_path": "/booking", "view": "list", "toggle_view": "1"}
    )

    assert _resources_query(api) == {"page": 1, "per_page": 12}


def test_a_chip_toggles_its_tag_and_resets_the_page():
    added, add_api = _catalogue({"tags": "quiet", "toggle_tag": "sunny", "page": "3"})
    removed, remove_api = _catalogue({"tags": "quiet,sunny", "toggle_tag": "quiet"})

    assert _resources_query(add_api)["tags"] == "quiet,sunny"
    assert _resources_query(add_api)["page"] == 1
    assert _resources_query(remove_api)["tags"] == "sunny"
    assert added["filters"]["tags"] == ["quiet", "sunny"]


def test_the_view_switch_flips_grid_and_list():
    assert _catalogue({"view": "grid", "toggle_view": "1"})[0]["view_mode"] == "list"
    assert _catalogue({"view": "list", "toggle_view": "1"})[0]["view_mode"] == "grid"
    assert _catalogue({"view": "list"})[0]["view_mode"] == "list"
    assert _catalogue({"view": "bogus"})[0]["view_mode"] == "grid"


def test_facets_and_options_are_resolved_through_the_descriptor():
    context, api = _catalogue({"availability_to": "2026-11-09"})

    assert [facet["key"] for facet in context["facets"]] == [
        "type",
        "tags",
        "availability",
    ]
    assert context["facets"][0]["options"] == [
        {"value": "specialist", "label": "Specialist"}
    ]
    assert context["filters"]["availability_to"] == "2026-11-09"


def test_a_card_has_its_link_price_unit_spots_and_labelled_tags():
    context, _api = _catalogue({"tags": "quiet"})

    card = context["resources"][0]
    assert card["href"] == "/booking/dr-smith"
    assert card["price"].label == "€50.00"
    assert card["price_unit"] == "session"
    assert card["capacity"] == 3
    assert card["tags"] == [{"slug": "quiet", "label": "Quiet", "active": True}]


def test_a_resource_without_pricing_shows_its_bare_price():
    bare = {**FakeBookingApi().answers["resources"]["items"][0], "pricing": None}
    context, _api = _catalogue(api=FakeBookingApi(resources={"items": [bare]}))

    assert context["resources"][0]["price"].label == "€50.00"


def test_card_prices_are_in_the_app_default_currency_read_once():
    resource = {**FakeBookingApi().answers["resources"]["items"][0], "currency": "GBP"}
    checkout_api = FakeCheckoutApi(default_currency="USD")
    context, _api = _catalogue(
        api=FakeBookingApi(resources={"items": [resource, resource]}),
        checkout_api=checkout_api,
    )

    assert [card["price"].label for card in context["resources"]] == [
        "$50.00",
        "$50.00",
    ]
    assert checkout_api.called("default_currency") == [("default_currency",)]


def test_states_error_empty_and_pager():
    failed, _api = _catalogue(api=FakeBookingApi(resources=ThemeApiError(500, "boom")))
    silent, _api = _catalogue(api=FakeBookingApi(resources=ThemeApiError(500, "")))
    empty, _api = _catalogue(api=FakeBookingApi(resources={"items": [], "pages": 1}))
    paged, _api = _catalogue(
        {"page": "2"}, api=FakeBookingApi(resources={"items": [], "pages": 3})
    )

    assert failed["state"] == "error" and failed["error"] == "boom"
    assert silent["error"] == "Failed to load resources"
    assert empty["state"] == "empty" and empty["pager"] is None
    assert paged["pager"] == {"current": 2, "total": 3, "previous": 1, "next": 3}


def test_the_fragment_uses_the_posted_page_path_as_the_form_action():
    api = FakeBookingApi()

    context = BookingCatalogue(api.factory, FakeCheckoutApi().factory).fragment_context(
        FakeThemeRequest(
            {"catalog_path": "/booking", "q": "smith"},
            path="/_render/_fragment/booking/resources",
        )
    )

    assert context["component_context"]["form_action"] == "/booking"
    assert _resources_query(api)["q"] == "smith"
