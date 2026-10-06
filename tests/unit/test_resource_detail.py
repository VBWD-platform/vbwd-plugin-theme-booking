"""S152-09 — BookingResourceDetail (``BookingResourceDetail.vue``) and its slot picker.

The resource comes from ``GET /api/v1/booking/resources/<route slug>``; any refusal
is the SPA's "Resource not found". A fixed-slot resource picks a date whose
slots load as a fragment over ``GET …/availability?date=`` (the SPA's
``fetchAvailability``); a flexible one (no slot duration) picks check-in / out.
"Book Now" submits a GET form to ``/<bookingFormSlug>/<slug>`` with ``date`` +
``start`` / ``end`` (or ``end_date``) — the SPA's ``router.push`` query.
"""
from datetime import date

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_booking.tests.unit.fakes import FLEXIBLE_RESOURCE, FakeBookingApi
from plugins.theme_booking.theme_booking.resource_detail import (
    BookingResourceDetail,
    SlotPicker,
    format_slot_time,
)
from plugins.theme_checkout.tests.unit.fakes import FakeCheckoutApi, FakeThemeRequest

TODAY = date(2026, 10, 4)


def _detail(api=None, slug="dr-smith", form_slug="booking-form", checkout_api=None):
    api = api or FakeBookingApi()
    checkout_api = checkout_api or FakeCheckoutApi()
    context = BookingResourceDetail(
        form_slug, api.factory, checkout_api.factory, today=lambda: TODAY
    ).build_context({}, {}, {"slug": slug}, FakeThemeRequest(path=f"/booking/{slug}"))
    return context, api


def test_the_resource_of_the_route_slug_is_loaded():
    context, api = _detail()

    assert api.called("resource") == [("resource", "dr-smith")]
    assert context["state"] == "resource"
    resource = context["resource"]
    assert resource["name"] == "Dr. Smith"
    assert resource["price"].label == "€50.00" and resource["price_unit"] == "session"
    assert resource["categories"] == ["Health"]


def test_the_price_is_in_the_app_default_currency():
    resource = {**FakeBookingApi().answers["resource"], "currency": "GBP"}
    context, _api = _detail(
        FakeBookingApi(resource=resource),
        checkout_api=FakeCheckoutApi(default_currency="USD"),
    )

    assert context["resource"]["price"].label == "$50.00"


def test_the_gallery_starts_on_the_primary_image():
    resource = _detail()[0]["resource"]

    assert resource["images"] == [
        {"url": "/uploads/smith.png", "alt": "front"},
        {"url": "/uploads/room.png", "alt": ""},
    ]
    assert resource["active_image_url"] == "/uploads/smith.png"
    assert resource["show_header_icon"] is False


def test_without_images_the_header_shows_the_icon():
    api = FakeBookingApi(
        resource={**FakeBookingApi().answers["resource"], "images": []}
    )

    assert _detail(api)[0]["resource"]["show_header_icon"] is True


def test_the_form_targets_the_configured_booking_form_route():
    context, _api = _detail(form_slug="reserve")

    assert context["form_action"] == "/reserve/dr-smith"
    assert context["slots_url"] == "/_render/_fragment/booking/slots"
    assert context["today"] == "2026-10-04"
    assert context["is_flexible"] is False


def test_a_flexible_resource_picks_check_in_and_out():
    api = FakeBookingApi(resource=FLEXIBLE_RESOURCE)

    assert _detail(api, slug="seaside-room")[0]["is_flexible"] is True


def test_any_refusal_is_resource_not_found():
    context, _api = _detail(FakeBookingApi(resource=ThemeApiError(500, "down")))

    assert context["state"] == "not_found"


def test_tags_and_custom_fields_ride_along_only_with_content():
    plain = _detail()[0]["resource"]
    tagged_api = FakeBookingApi(
        resource={**FakeBookingApi().answers["resource"], "tags": ["quiet"]}
    )
    tagged = _detail(tagged_api)[0]["resource"]

    assert plain["tags_custom_fields"] is None
    assert tagged["tags_custom_fields"]["tags"] == ["quiet"]


def _slots(query, api=None):
    api = api or FakeBookingApi()
    context = SlotPicker(api.factory).fragment_context(
        FakeThemeRequest(query, path="/_render/_fragment/booking/slots")
    )
    return context, api


def test_slots_load_for_the_picked_date():
    context, api = _slots({"resource": "dr-smith", "date": "2026-11-02"})

    assert api.called("availability") == [("availability", "dr-smith", "2026-11-02")]
    assert context["state"] == "slots"
    assert context["slots"] == [
        {
            "label": "09:00 – 09:30",
            "capacity": 2,
            "full": False,
            "start": "09:00",
            "end": "09:30",
        },
        {
            "label": "09:30 – 10:00",
            "capacity": 0,
            "full": True,
            "start": "2026-11-02T09:30:00",
            "end": "2026-11-02T10:00:00",
        },
    ]


def test_no_date_asks_for_one_and_no_slots_says_so():
    picked_nothing, api = _slots({"resource": "dr-smith", "date": ""})
    empty, _api = _slots(
        {"resource": "dr-smith", "date": "2026-11-07"},
        FakeBookingApi(availability={"slots": []}),
    )
    refused, _api = _slots(
        {"resource": "dr-smith", "date": "2026-11-07"},
        FakeBookingApi(availability=ThemeApiError(400, "bad date")),
    )

    assert picked_nothing["state"] == "pick_date" and api.called("availability") == []
    assert empty["state"] == "no_slots"
    assert refused["state"] == "no_slots"


def test_format_slot_time_mirrors_the_spa():
    assert format_slot_time({"start": "09:00", "end": "09:30"}) == "09:00 – 09:30"
    assert format_slot_time({"date": "2026-11-02"}) == "2026-11-02"
    assert format_slot_time({}) == ""
