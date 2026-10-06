"""S152-09 — the booking pay page's checkout source (``BookingCheckout.vue``).

The SPA pays a booking on its own page, not through ``/checkout``: the pending
booking (``store.pendingCheckout``, set by BookingForm) is priced from the
resource's ``pricing`` block — brutto per unit, a BOOKING-scope coupon on it —
and ``handlePay`` posts ``POST /api/v1/booking/checkout``. Here the pending
booking arrives as the ``pending`` form field (the runtime reads it from
``sessionStorage``); custom fields are typed by the resource's schema the way
the SPA's ``v-model`` types them (text, ``.number``, checkbox ``true``; untouched
fields are absent). theme_checkout's island and confirm fragments drive this
source, so the email/billing/payment/terms blocks and the post-submit dispatch
are the shared ones.
"""
import json
from decimal import Decimal

import pytest

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_booking.tests.unit.fakes import FakeBookingApi
from plugins.theme_booking.theme_booking.checkout_source import (
    BookingCheckout,
    booking_payload,
)
from plugins.theme_checkout.tests.unit.fakes import FakeCheckoutApi, FakeThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_sources import (
    CheckoutRouteContext,
)

PENDING_FIELDS = {
    "resource_slug": "dr-smith",
    "start_at": "2026-11-02T09:00:00",
    "end_at": "2026-11-02T09:30:00",
    "custom_fields.symptoms": "Headache",
    "custom_fields.visits": "2",
    "custom_fields.insured": "on",
    "notes": "E2E test booking",
}
SCHEMA = FakeBookingApi().answers["resource"]["custom_fields_schema"]
CONTEXT = CheckoutRouteContext(source="booking")


def _request(fields=PENDING_FIELDS):
    return FakeThemeRequest({"pending": json.dumps(fields), "source": "booking"})


def _checkout(api=None, checkout_api=None):
    api = api or FakeBookingApi()
    checkout_api = checkout_api or FakeCheckoutApi()
    return BookingCheckout(api.factory, checkout_api.factory), api, checkout_api


def test_the_source_is_booking_without_a_cart():
    source = _checkout()[0].checkout_source()

    assert source.id == "booking"
    assert source.cart_key is None
    assert source.matches(CONTEXT) and not source.matches(CheckoutRouteContext())
    assert source.summary_template == "booking/pay_summary.html.j2"


def test_the_payload_types_custom_fields_like_the_spa_v_model():
    assert booking_payload(PENDING_FIELDS, SCHEMA) == {
        "resource_slug": "dr-smith",
        "start_at": "2026-11-02T09:00:00",
        "end_at": "2026-11-02T09:30:00",
        "custom_fields": {"symptoms": "Headache", "visits": 2, "insured": True},
        "notes": "E2E test booking",
    }


def test_untouched_fields_and_empty_notes_stay_out_of_the_payload():
    sparse = {
        "resource_slug": "dr-smith",
        "start_at": "2026-11-02T09:00:00",
        "end_at": "2026-11-02T09:30:00",
        "custom_fields.symptoms": "",
        "custom_fields.visits": "two",
        "notes": "",
    }

    assert booking_payload(sparse, SCHEMA) == {
        "resource_slug": "dr-smith",
        "start_at": "2026-11-02T09:00:00",
        "end_at": "2026-11-02T09:30:00",
        "custom_fields": {},
    }


def test_the_summary_prices_the_resource_brutto():
    checkout, api, _checkout_api = _checkout()

    summary = checkout.load_summary(_request(), CONTEXT)

    assert api.called("resource") == [("resource", "dr-smith")]
    assert summary.order_total == Decimal("50.00")
    assert summary.currency == "EUR"
    assert summary.discount_amount == Decimal("0")
    view = summary.template_context
    assert view["resource"]["name"] == "Dr. Smith"
    assert view["resource"]["href"] == "/booking/dr-smith"
    assert view["resource"]["price"].label == "€50.00"
    assert view["date_time"] == "11/2/2026, 9:00:00 AM — 11/2/2026, 9:30:00 AM"
    assert view["notes"] == "E2E test booking"
    assert view["custom_fields"] == [
        ("symptoms", "Headache"),
        ("visits", "2"),
        ("insured", "true"),
    ]


def test_a_booking_coupon_discounts_the_brutto_total():
    checkout_api = FakeCheckoutApi(
        validate_coupon={"valid": True, "discount_amount": "10.00"}
    )
    checkout, _api, _checkout_api = _checkout(checkout_api=checkout_api)

    summary = checkout.load_summary(
        _request(), CheckoutRouteContext(source="booking", coupon_code="SAVE10")
    )

    assert checkout_api.called("validate_coupon") == [
        ("validate_coupon", "SAVE10", 50.0, "BOOKING")
    ]
    assert summary.order_total == Decimal("40.00")
    assert summary.discount_amount == Decimal("10.00")
    assert summary.applied_coupon_code == "SAVE10"


def test_a_resource_without_pricing_charges_its_bare_price():
    bare = {**FakeBookingApi().answers["resource"], "pricing": None, "price": "12.50"}
    checkout, _api, _checkout_api = _checkout(FakeBookingApi(resource=bare))

    assert checkout.load_summary(_request(), CONTEXT).order_total == Decimal("12.50")


@pytest.mark.parametrize(
    "pending", ["", "not json", json.dumps({"resource_slug": "x"})]
)
def test_no_pending_booking_is_booking_not_found(pending):
    checkout = _checkout()[0]

    with pytest.raises(ThemeApiError) as refusal:
        checkout.load_summary(FakeThemeRequest({"pending": pending}), CONTEXT)

    assert refusal.value.status == 404


def test_submit_posts_the_booking_checkout_with_the_applied_coupon():
    checkout, api, _checkout_api = _checkout()

    result = checkout.submit(
        _request(),
        CheckoutRouteContext(source="booking", coupon_code="SAVE10"),
        "stripe",
    )

    assert api.called("checkout") == [
        (
            "checkout",
            {**booking_payload(PENDING_FIELDS, SCHEMA), "coupon_code": "SAVE10"},
        )
    ]
    assert result == {"invoice": {"id": "inv-9", "invoice_number": "BK-1"}}


def test_submit_without_a_coupon_sends_none():
    checkout, api, _checkout_api = _checkout()

    checkout.submit(_request(), CONTEXT, "invoice")

    assert "coupon_code" not in api.called("checkout")[0][1]


def test_submit_refusals_reach_the_buyer():
    checkout, _api, _checkout_api = _checkout(
        FakeBookingApi(checkout=ThemeApiError(400, "Not enough capacity"))
    )

    with pytest.raises(ThemeApiError) as refusal:
        checkout.submit(_request(), CONTEXT, "invoice")

    assert refusal.value.message == "Not enough capacity"
