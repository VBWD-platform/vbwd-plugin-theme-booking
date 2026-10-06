"""S152-09 — BookingForm (``BookingForm.vue``): the slot summary and the custom fields.

The slot rides in the query from the detail page. ``start_at`` / ``end_at`` are
built exactly as the SPA builds them (``<date>T<HH:MM>:00`` — a slot boundary
that arrives as an ISO datetime is cut to its clock time, ``slotClockTime``; a
flexible stay is check-in 14:00 → check-out 11:00). The header prints the app
default currency (``useAppConfigStore().defaultCurrency``, ``GET
/api/v1/config``). Each field of ``custom_fields_schema`` gets the SPA's input
(text for ``string``/``text``, number for ``integer``, checkbox for
``boolean``, a bare label otherwise). "Confirm Booking" posts the form to
``/booking/<slug>/book/pay``.
"""
from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_booking.tests.unit.fakes import FLEXIBLE_RESOURCE, FakeBookingApi
from plugins.theme_booking.theme_booking.booking_form import BookingForm
from plugins.theme_checkout.tests.unit.fakes import FakeCheckoutApi, FakeThemeRequest

FIXED_QUERY = {"date": "2026-11-02", "start": "09:00", "end": "09:30"}


ISO_QUERY = {
    "date": "2026-11-02",
    "start": "2026-11-02T09:00:00",
    "end": "2026-11-02T09:30:00",
}


def _form(query=FIXED_QUERY, api=None, slug="dr-smith", checkout_api=None):
    api = api or FakeBookingApi()
    checkout_api = checkout_api or FakeCheckoutApi()
    context = BookingForm(api.factory, checkout_api.factory).build_context(
        {}, {}, {"slug": slug}, FakeThemeRequest(query, path=f"/booking-form/{slug}")
    )
    return context, api


def test_the_fixed_slot_summary_and_times():
    context, api = _form()

    assert api.called("resource") == [("resource", "dr-smith")]
    assert context["state"] == "resource"
    assert context["display_date_time"] == "2026-11-02  09:00 – 09:30"
    assert context["start_at"] == "2026-11-02T09:00:00"
    assert context["end_at"] == "2026-11-02T09:30:00"
    assert context["resource_slug"] == "dr-smith"
    assert context["pay_path"] == "/booking/dr-smith/book/pay"
    assert context["back_href"] == "/booking/dr-smith"


def test_an_iso_slot_boundary_is_cut_to_its_clock_time():
    context, _api = _form(ISO_QUERY)

    assert context["display_date_time"] == "2026-11-02  09:00 – 09:30"
    assert context["start_at"] == "2026-11-02T09:00:00"
    assert context["end_at"] == "2026-11-02T09:30:00"


def test_a_flexible_stay_is_check_in_fourteen_to_check_out_eleven():
    context, _api = _form(
        {"date": "2026-11-02", "end_date": "2026-11-05"},
        FakeBookingApi(resource=FLEXIBLE_RESOURCE),
        slug="seaside-room",
    )

    assert context["display_date_time"] == "2026-11-02 → 2026-11-05"
    assert context["start_at"] == "2026-11-02T14:00:00"
    assert context["end_at"] == "2026-11-05T11:00:00"


def test_the_header_line_is_type_price_currency_and_unit():
    resource = _form()[0]["resource"]

    assert resource["name"] == "Dr. Smith"
    assert resource["summary_line"] == "specialist · 50.00 EUR / session"


def test_the_header_currency_is_the_app_default_not_the_resources():
    resource = {**FakeBookingApi().answers["resource"], "currency": "GBP"}
    context, _api = _form(
        api=FakeBookingApi(resource=resource),
        checkout_api=FakeCheckoutApi(default_currency="USD"),
    )

    assert context["resource"]["summary_line"] == "specialist · 50.00 USD / session"


def test_each_custom_field_gets_the_spa_input():
    fields = _form()[0]["custom_fields"]

    assert fields == [
        {"id": "symptoms", "label": "Symptoms", "required": True, "input": "text"},
        {"id": "visits", "label": "Visits", "required": False, "input": "number"},
        {"id": "insured", "label": "Insured", "required": False, "input": "checkbox"},
    ]


def test_an_unknown_field_type_is_a_bare_label():
    resource = {
        **FakeBookingApi().answers["resource"],
        "custom_fields_schema": [
            {"id": "when", "label": "When", "type": "date", "required": False}
        ],
    }

    assert (
        _form(api=FakeBookingApi(resource=resource))[0]["custom_fields"][0]["input"]
        is None
    )


def test_any_refusal_is_resource_not_found():
    assert (
        _form(api=FakeBookingApi(resource=ThemeApiError(404, "x")))[0]["state"]
        == "not_found"
    )
