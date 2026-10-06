"""S152-09 — BookingSuccess (``BookingSuccess.vue``) on the ``booking-success`` CMS page.

The widget sits in a CMS layout area, so theme_cms renders it as a personalised
region: the anonymous page shows the pending banner without an API call; the
viewer's re-render reads ``GET /api/v1/user/invoices/<invoice_id|invoice>`` with
the bearer. The booking line item is found by ``metadata.plugin == "booking"``
— the key the invoice API serialises (the SPA reads ``extra_data``, which the API
never sends: SPA bug, reported). Its resource comes from the booking API,
falling back to the names stored on the line.
"""
from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_booking.tests.unit.fakes import FakeBookingApi
from plugins.theme_booking.theme_booking.success import BookingSuccess
from plugins.theme_checkout.tests.unit.fakes import FakeCheckoutApi, FakeThemeRequest

BOOKING_LINE = {
    "description": "Dr. Smith — 2026-11-02 09:00",
    "metadata": {
        "plugin": "booking",
        "resource_slug": "dr-smith",
        "resource_name": "Dr. Smith",
        "resource_type": "specialist",
        "start_at": "2026-11-02T09:00:00",
        "end_at": "2026-11-02T09:30:00",
        "custom_fields": {"symptoms": "Headache", "insured": True},
        "notes": "E2E test booking",
    },
}
INVOICE = {
    "id": "inv-9",
    "invoice_number": "BK-1A2B3C4D",
    "status": "PAID",
    "amount": "50.00",
    "subtotal": "42.02",
    "tax_amount": "7.98",
    "total_amount": "50.00",
    "currency": "EUR",
    "paid_at": "2026-11-01T12:00:00",
    "line_items": [
        {"description": "Other", "metadata": {"plugin": "shop"}},
        BOOKING_LINE,
    ],
}


def _success(query=None, user_id="user-a", api=None, checkout_api=None):
    api = api or FakeBookingApi()
    checkout_api = checkout_api or FakeCheckoutApi(invoice={"invoice": INVOICE})
    context = BookingSuccess(api.factory, checkout_api.factory).build_context(
        {},
        {},
        {},
        FakeThemeRequest(
            {"invoice_id": "inv-9"} if query is None else query,
            user_id=user_id,
            path="/booking-success",
        ),
    )
    return context, api, checkout_api


def test_anonymous_render_is_the_pending_banner_without_an_api_call():
    context, api, checkout_api = _success(user_id=None)

    assert context["status"] == "pending"
    assert context["title_key"] == "booking.success.titlePending"
    assert context["message_key"] == "booking.success.messagePending"
    assert context["invoice"] is None and context["booking"] is None
    assert checkout_api.calls == [] and api.calls == []


def test_a_paid_invoice_shows_its_details_and_breakdown():
    context, _api, checkout_api = _success()

    assert checkout_api.called("invoice") == [("invoice", "inv-9")]
    assert context["status"] == "paid"
    assert context["title_key"] == "booking.success.titlePaid"
    assert context["message_key"] == "booking.success.messagePaid"
    invoice = context["invoice"]
    assert invoice["number"] == "BK-1A2B3C4D"
    assert invoice["paid_at"] == "11/1/2026, 12:00:00 PM"
    assert invoice["breakdown"] == {
        "net": "€42.02",
        "taxes": [{"label_name": "TAX", "rate": 0, "amount": "€7.98"}],
        "gross": "€50.00",
    }


def test_the_authorized_title_keeps_the_pending_message():
    authorized = {**INVOICE, "status": "AUTHORIZED"}
    context, _api, _checkout_api = _success(
        checkout_api=FakeCheckoutApi(invoice=authorized)
    )

    assert context["title_key"] == "booking.success.titleAuthorized"
    assert context["message_key"] == "booking.success.messagePending"


def test_the_booking_line_brings_the_resource_and_booking_rows():
    context, api, _checkout_api = _success({"invoice": "inv-9"})

    assert api.called("resource") == [("resource", "dr-smith")]
    booking = context["booking"]
    assert booking["resource"]["name"] == "Dr. Smith"
    assert booking["resource"]["href"] == "/booking/dr-smith"
    assert booking["date_time"] == "11/2/2026, 9:00:00 AM — 11/2/2026, 9:30:00 AM"
    assert booking["custom_fields"] == [("symptoms", "Headache"), ("insured", "true")]
    assert booking["notes"] == "E2E test booking"


def test_an_unreadable_resource_falls_back_to_the_line_names():
    context, _api, _checkout_api = _success(
        api=FakeBookingApi(resource=ThemeApiError(404, "gone"))
    )

    resource = context["booking"]["resource"]
    assert resource["name"] == "Dr. Smith" and resource["resource_type"] == "specialist"
    assert resource["description"] is None


def test_an_invoice_without_a_booking_line_has_no_booking_card():
    other = {**INVOICE, "line_items": [{"metadata": {"plugin": "shop"}}]}
    context, api, _checkout_api = _success(checkout_api=FakeCheckoutApi(invoice=other))

    assert context["booking"] is None and api.calls == []


def test_an_unreadable_invoice_and_a_missing_id_stay_pending():
    refused, _api, _checkout_api = _success(
        checkout_api=FakeCheckoutApi(invoice=ThemeApiError(404, "no"))
    )
    missing, _api, checkout_api = _success(query={})

    assert refused["status"] == "pending" and refused["invoice"] is None
    assert missing["status"] == "pending" and checkout_api.calls == []


def test_an_untaxed_invoice_without_currency_uses_the_operating_currency():
    untaxed = {
        **INVOICE,
        "currency": None,
        "tax_amount": "0.00",
        "subtotal": None,
        "total_amount": None,
        "amount": "20.00",
    }
    context, _api, _checkout_api = _success(
        checkout_api=FakeCheckoutApi(invoice=untaxed)
    )

    assert context["invoice"]["breakdown"] == {
        "net": "€20.00",
        "taxes": [],
        "gross": "€20.00",
    }
