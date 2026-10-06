"""S152-09 — the booking Playwright specs' selectors exist in the themed output (D2 / R4).

Every row names the selector or text verbatim in a spec, the spec and the line
that uses it (documentation), the themed output that page step reaches and a
regex the output must match. The drift guard fails when a spec stops using a
pinned selector (skips without fe-user). Text selectors (``text=Invoice``, the
``booking-checkout.spec.ts`` method labels) are kept verbatim. Steps owned by
theme_checkout's shared fragments (the email-check sign-up / login forms) are
covered by its own contract. ``booking-schedule-visibility.spec.ts`` drives the
API only.

The confirmation rows (``booking-checkout.spec.ts:270-287``,
``expectBookingConfirmation``) are checked against the paid invoice's themed
``/checkout/confirmation`` with theme_booking's BookingConfirmationDetails
section — the page the SPA lands on after paying (S152 16b).
"""
import pytest

from plugins.theme_booking.tests.integration.booking_seed import (
    next_monday,
    seed_booking_journey,
)
from plugins.theme_booking.tests.integration.test_booking_flow import (
    PAY_FORM,
    _pay_fields,
    _pending_fields,
)
from plugins.theme_checkout.tests.integration.themed_stack import (
    FE_USER_ROOT,
    RENDER,
    confirmation_page,
    contract_drift,
    contract_misses,
    regions_html,
    themed_page_gotos,
)

BOOKING = "vue/tests/e2e/booking.spec.ts"
CHECKOUT = "vue/tests/e2e/booking-checkout.spec.ts"
INVOICE = "vue/tests/e2e/booking-invoice-payment.spec.ts"
AUTHORIZE = "vue/tests/e2e/booking-authorize.spec.ts"
SCHEDULE = "vue/tests/e2e/booking-schedule-visibility.spec.ts"
DATE_INPUT = r'<input type="date" name="date"'
FREE_SLOT = r'<button type="button" class="booking-slot" data-vbwd-booking-slot'
CTA = r'class="ghrm-cta-btn"'
TEXT_FIELD = r'(?s)<div class="booking-form__field">\s*<label[^>]*>.*?</label>\s*<input[^>]*type="text"'
NUMBER_FIELD = r'(?s)<div class="booking-form__field">\s*<label[^>]*>.*?</label>\s*<input[^>]*type="number"'
CHECKBOX_FIELD = r'<label class="booking-form__checkbox">\s*<input[^>]*type="checkbox"'
TERMS_CHECKBOX = (
    r'data-testid="terms-checkbox">\s*<label[^>]*>\s*<input type="checkbox"'
)
PAY_BUTTON = r'class="btn primary pay-button"'
# ``.booking-price`` inside its ``ancestor::div[contains(@class,"card")]`` section.
BOOKING_CARD_PRICE = r'(?s)<div class="card" data-confirmation-section="booking">.*?class="booking-price"'


def _testid(name):
    return rf'data-testid="{name}"'


BOOKING_CONTRACT = [
    ('a[href*="/booking/"]', BOOKING, 90, "catalogue", r'<a href="/booking/[^"]+"'),
    ("E2E Playwright Resource", BOOKING, 100, "detail", r"E2E Playwright Resource"),
    (
        '[data-testid="price-amount"]',
        BOOKING,
        109,
        "detail",
        r'data-testid="price-amount">€50\.00<',
    ),
    ('input[type="date"]', BOOKING, 110, "detail", DATE_INPUT),
    ("E2E Playwright Resource", BOOKING, 119, "form", r"E2E Playwright Resource"),
    (
        '[data-testid="checkout-title"]',
        BOOKING,
        139,
        "pay_page",
        _testid("checkout-title"),
    ),
    ('input[type="date"]', BOOKING, 146, "detail", DATE_INPUT),
    (".booking-slot:not(.full)", BOOKING, 150, "slots", FREE_SLOT),
    (".ghrm-cta-btn", BOOKING, 151, "detail", CTA),
    (".ghrm-cta-btn", BOOKING, 154, "form", CTA),
    ('input[type="email"]', BOOKING, 158, "anonymous_island", r'<input type="email"'),
]
CHECKOUT_CONTRACT = [
    ('input[type="date"]', CHECKOUT, 61, "detail", DATE_INPUT),
    (".booking-slot:not(.full)", CHECKOUT, 72, "slots", FREE_SLOT),
    (".ghrm-cta-btn", CHECKOUT, 77, "detail", CTA),
    ('.booking-form__field input[type="text"]', CHECKOUT, 90, "form", TEXT_FIELD),
    ('.booking-form__field input[type="number"]', CHECKOUT, 96, "form", NUMBER_FIELD),
    (
        '.booking-form__checkbox input[type="checkbox"]',
        CHECKOUT,
        103,
        "form",
        CHECKBOX_FIELD,
    ),
    ("textarea", CHECKOUT, 110, "form", r'<textarea name="notes"'),
    (".ghrm-cta-btn", CHECKOUT, 116, "form", CTA),
    (
        '[data-testid="billing-address-block"]',
        CHECKOUT,
        130,
        "island",
        _testid("billing-address-block"),
    ),
    (
        '[data-testid="billing-street"]',
        CHECKOUT,
        131,
        "island",
        _testid("billing-street"),
    ),
    (
        '[data-testid="billing-first-name"]',
        CHECKOUT,
        134,
        "island",
        _testid("billing-first-name"),
    ),
    (
        '[data-testid="billing-last-name"]',
        CHECKOUT,
        138,
        "island",
        _testid("billing-last-name"),
    ),
    ('[data-testid="billing-city"]', CHECKOUT, 145, "island", _testid("billing-city")),
    ('[data-testid="billing-zip"]', CHECKOUT, 146, "island", _testid("billing-zip")),
    (
        '[data-testid="billing-country"]',
        CHECKOUT,
        147,
        "island",
        _testid("billing-country"),
    ),
    (
        '[data-testid="payment-methods-block"]',
        CHECKOUT,
        154,
        "island",
        _testid("payment-methods-block"),
    ),
    (
        "'Pay with Stripe'",
        CHECKOUT,
        122,
        "island",
        r'class="method-name">Pay with Stripe</label>',
    ),
    ("'Invoice'", CHECKOUT, 123, "island", r'class="method-name">Invoice</label>'),
    (
        '[data-testid="terms-checkbox"] input[type="checkbox"]',
        CHECKOUT,
        170,
        "island",
        TERMS_CHECKBOX,
    ),
    (".pay-button", CHECKOUT, 176, "island", PAY_BUTTON),
    (
        '[data-testid="checkout-confirmation"]',
        CHECKOUT,
        270,
        "confirmation",
        _testid("checkout-confirmation"),
    ),
    (
        '[data-testid="confirmation-banner"]',
        CHECKOUT,
        271,
        "confirmation",
        _testid("confirmation-banner"),
    ),
    (".confirmation-mono", CHECKOUT, 274, "confirmation", r'confirmation-mono">BK-'),
    (".status-badge", CHECKOUT, 275, "confirmation", r'class="status-badge paid"'),
    ("'50.00'", CHECKOUT, 276, "confirmation", r"50\.00"),
    (".booking-price", CHECKOUT, 279, "confirmation", BOOKING_CARD_PRICE),
    (
        ".resource-name-link",
        CHECKOUT,
        280,
        "confirmation",
        r'<a href="/booking/[^"]+" class="resource-name-link">',
    ),
    ("50 EUR", CHECKOUT, 282, "confirmation", r'class="booking-price">\s*50 EUR/'),
    ("Date & time", CHECKOUT, 283, "confirmation", r"(?i)Date &amp; time"),
    ("'E2E test booking'", CHECKOUT, 284, "confirmation", r"E2E test booking"),
    # getByText('Symptoms') is case-insensitive: the field key prints as entered.
    (
        "'Symptoms'",
        CHECKOUT,
        287,
        "confirmation",
        r'(?i)detail-label">\s*symptoms\s*<',
    ),
]

INVOICE_CONTRACT = [
    ('input[type="date"]', INVOICE, 81, "detail", DATE_INPUT),
    (".booking-slot:not(.full)", INVOICE, 88, "slots", FREE_SLOT),
    (".ghrm-cta-btn", INVOICE, 92, "detail", CTA),
    ('.booking-form__field input[type="text"]', INVOICE, 102, "form", TEXT_FIELD),
    ("textarea", INVOICE, 108, "form", r'<textarea name="notes"'),
    (".ghrm-cta-btn", INVOICE, 113, "form", CTA),
    (
        '[data-testid="billing-first-name"]',
        INVOICE,
        123,
        "island",
        _testid("billing-first-name"),
    ),
    (
        '[data-testid="billing-last-name"]',
        INVOICE,
        128,
        "island",
        _testid("billing-last-name"),
    ),
    (
        '[data-testid="billing-street"]',
        INVOICE,
        133,
        "island",
        _testid("billing-street"),
    ),
    ('[data-testid="billing-city"]', INVOICE, 138, "island", _testid("billing-city")),
    ('[data-testid="billing-zip"]', INVOICE, 143, "island", _testid("billing-zip")),
    (
        '[data-testid="billing-country"]',
        INVOICE,
        148,
        "island",
        _testid("billing-country"),
    ),
    ("text=Invoice", INVOICE, 155, "island", r'class="method-name">Invoice</label>'),
    (
        '[data-testid="terms-checkbox"] input[type="checkbox"]',
        INVOICE,
        162,
        "island",
        TERMS_CHECKBOX,
    ),
    (".pay-button", INVOICE, 168, "island", PAY_BUTTON),
]
AUTHORIZE_CONTRACT = [
    ("/booking/success", AUTHORIZE, 106, "spa_success_route", r"<html"),
    ("nav a", AUTHORIZE, 111, "spa_success_route", r"(?s)<nav[^>]*>.*?<a "),
]
CONTRACT = BOOKING_CONTRACT + CHECKOUT_CONTRACT + INVOICE_CONTRACT + AUTHORIZE_CONTRACT


def _paid_booking_invoice(client, bearer, admin_headers, resource):
    checkout = client.post(
        "/api/v1/booking/checkout",
        json={
            "resource_slug": resource["slug"],
            "start_at": f"{next_monday()}T10:00:00",
            "end_at": f"{next_monday()}T10:30:00",
            "custom_fields": {"symptoms": "E2E test value"},
            "notes": "E2E test booking",
        },
        headers=bearer,
    )
    assert checkout.status_code == 201, checkout.get_json()
    invoice_id = checkout.get_json()["invoice_id"]
    paid = client.post(
        f"/api/v1/admin/invoices/{invoice_id}/mark-paid",
        json={"payment_reference": "S152-09", "payment_method": "invoice"},
        headers=admin_headers,
    )
    assert paid.status_code == 200, paid.get_json()
    return invoice_id


def _text(response):
    assert response.status_code == 200, response.get_data(as_text=True)[:500]
    return response.get_data(as_text=True)


def test_every_booking_spec_selector_is_in_the_themed_output(
    client, bearer, admin_headers, cms
):
    confirmation_page(cms, client)
    resource = seed_booking_journey(client, admin_headers, cms)
    slug = resource["slug"]
    pending = _pending_fields(client, resource)
    invoice_id = _paid_booking_invoice(client, bearer, admin_headers, resource)
    outputs = {
        "catalogue": _text(client.get("/booking", headers=RENDER)),
        "detail": _text(client.get(f"/booking/{slug}", headers=RENDER)),
        "slots": _text(
            client.get(
                "/_render/_fragment/booking/slots",
                query_string={"resource": slug, "date": next_monday()},
            )
        ),
        "form": _text(
            client.get(
                f"/booking-form/{slug}?date={next_monday()}&start=09:00&end=09:30",
                headers=RENDER,
            )
        ),
        "pay_page": _text(client.get(f"/booking/{slug}/book/pay", headers=RENDER)),
        "anonymous_island": _text(client.post(PAY_FORM, data=_pay_fields(pending))),
        "island": _text(
            client.post(PAY_FORM, data=_pay_fields(pending), headers=bearer)
        ),
        "confirmation": regions_html(
            client, bearer, f"/checkout/confirmation?invoice_id={invoice_id}"
        ),
        "spa_success_route": _text(client.get("/booking/success", headers=RENDER)),
    }

    assert contract_misses(CONTRACT, outputs) == []


def test_the_booking_spec_lines_still_use_these_selectors():
    if not (FE_USER_ROOT / BOOKING).is_file():
        pytest.skip("fe-user is not next to vbwd-backend (plugin CI)")

    assert contract_drift(CONTRACT) == []


def test_the_schedule_visibility_spec_drives_only_the_api():
    if not (FE_USER_ROOT / SCHEDULE).is_file():
        pytest.skip("fe-user is not next to vbwd-backend (plugin CI)")

    assert themed_page_gotos(SCHEDULE) == []
    assert "page.goto" not in (FE_USER_ROOT / SCHEDULE).read_text(encoding="utf-8")
