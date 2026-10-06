"""S152-09 — theme_booking on a real ``create_app`` (theme mode).

The booking journeys through the themed renderer, over the REAL booking,
checkout, cms and stripe plugins: the catalogue and its search fragment, the
resource detail, a day's slots, the booking form, the pay page; a full themed
booking paid by invoice (resource → slot → form → pay island → invoice →
confirmation redirect → BookingSuccess region after the admin marks it paid);
the Stripe method's HX-Redirect to the THEMED ``/pay/stripe`` whose create
fragment then reaches the (stubbed) Stripe SDK; and the fe-user toggle.
"""
import json
import re
from types import SimpleNamespace

import pytest
import stripe

from plugins.theme_booking.tests.integration.booking_seed import (
    RESOURCE_NAME,
    next_monday,
    seed_booking_journey,
)
from plugins.theme_booking.tests.integration.conftest import FE_USER_PLUGINS
from plugins.theme_checkout.tests.integration.themed_stack import (
    RENDER,
    regions_html,
)
from plugins.theme_checkout.tests.integration.payment.conftest import write_manifest

PAY_FORM = "/_render/_fragment/booking/pay-form"
PAY_SUBMIT = "/_render/_fragment/booking/pay-submit"
CONFIRMATION = re.compile(r"^/checkout/confirmation\?invoice_id=([0-9a-f-]+)$")
STRIPE_PAY = re.compile(r"^/pay/stripe\?invoice=([0-9a-f-]+)$")
ORIGIN = {"Origin": "https://booking.example"}
SESSION_URL = "https://checkout.stripe.test/c/pay/cs_test_booking"
CUSTOM_FIELD_VALUES = {
    "custom_fields.symptoms": "E2E test value",
    "custom_fields.visits": "2",
    "custom_fields.insured": "on",
    "notes": "E2E test booking",
}


@pytest.fixture
def resource(client, admin_headers, cms):
    return seed_booking_journey(client, admin_headers, cms)


def _page(client, path):
    response = client.get(path, headers=RENDER)
    assert response.status_code == 200, (path, response.get_data(as_text=True)[:500])
    return response.get_data(as_text=True)


def _first_free_slot(client, resource):
    html = client.get(
        "/_render/_fragment/booking/slots",
        query_string={"resource": resource["slug"], "date": next_monday()},
    ).get_data(as_text=True)
    match = re.search(
        r'<button type="button" class="booking-slot" data-vbwd-booking-slot '
        r'data-start="([^"]+)" data-end="([^"]+)">',
        html,
    )
    assert match, html
    return match.group(1), match.group(2)


def _pending_fields(client, resource):
    """What booking_runtime.js keeps: the booking form's fields, as the buyer filled them."""
    start, end = _first_free_slot(client, resource)
    form_page = _page(
        client,
        f"/booking-form/{resource['slug']}?date={next_monday()}&start={start}&end={end}",
    )
    hidden = dict(
        re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)">', form_page)
    )
    return {
        "resource_slug": hidden["resource_slug"],
        "start_at": hidden["start_at"],
        "end_at": hidden["end_at"],
        **CUSTOM_FIELD_VALUES,
    }


def _pay_fields(pending, **extra):
    return {"source": "booking", "pending": json.dumps(pending), **extra}


def test_the_catalogue_lists_and_searches_resources(client, resource):
    page = _page(client, "/booking")
    hit = client.get(
        "/_render/_fragment/booking/resources",
        query_string={"q": "Playwright", "catalog_path": "/booking"},
    ).get_data(as_text=True)
    miss = client.get(
        "/_render/_fragment/booking/resources",
        query_string={"q": "zzz-no-such-resource", "catalog_path": "/booking"},
    ).get_data(as_text=True)

    assert '<meta name="vbwd-frontend" content="theme">' in page
    assert f'data-testid="booking-resource-card-{resource["slug"]}"' in page
    assert re.search(
        rf'data-testid="booking-resource-name">\s*{RESOURCE_NAME}\s*<', hit
    )
    assert 'data-testid="booking-catalogue-empty"' in miss


def test_the_resource_detail_shows_name_price_and_the_date_picker(client, resource):
    html = _page(client, f"/booking/{resource['slug']}")

    assert re.search(rf'<h1 class="ghrm-detail-name">\s*{RESOURCE_NAME}\s*</h1>', html)
    assert re.search(r'data-testid="price-amount">€50\.00<', html)
    assert re.search(r'<input type="date" name="date"', html)
    assert f'action="/booking-form/{resource["slug"]}"' in html


def test_next_mondays_slots_come_from_the_availability_api(client, resource):
    start, end = _first_free_slot(client, resource)

    assert (start, end) == ("09:00", "09:30")


def test_the_booking_form_carries_the_slot_and_the_custom_fields(client, resource):
    html = _page(
        client,
        f"/booking-form/{resource['slug']}?date={next_monday()}&start=09:00&end=09:30",
    )

    assert re.search(rf"Book: {RESOURCE_NAME}", html)
    assert (
        f'<input type="hidden" name="start_at" value="{next_monday()}T09:00:00">'
        in html
    )
    assert 'name="custom_fields.symptoms" required' in html
    assert f'action="/booking/{resource["slug"]}/book/pay"' in html


def test_the_pay_page_without_a_pending_booking(client, resource, bearer):
    page = _page(client, f"/booking/{resource['slug']}/book/pay")
    island = client.post(PAY_FORM, data={"source": "booking"}, headers=bearer)

    assert re.search(r'<h1 data-testid="checkout-title">', page)
    assert 'class="cms-layout' not in page
    assert re.search(r"Booking not found\.", island.get_data(as_text=True))


def test_the_anonymous_pay_island_asks_to_sign_in(client, resource):
    island = client.post(PAY_FORM, data=_pay_fields(_pending_fields(client, resource)))
    html = island.get_data(as_text=True)

    assert island.status_code == 200, html
    assert 'type="email"' in html
    assert re.search(
        r'<li data-requirement="signIn">\s*Please log in or create an account', html
    )


def test_a_full_themed_booking_paid_by_invoice(client, bearer, admin_headers, resource):
    pending = _pending_fields(client, resource)

    island = client.post(PAY_FORM, data=_pay_fields(pending), headers=bearer)
    submitted = client.post(
        PAY_SUBMIT,
        data=_pay_fields(pending, payment_method="invoice", terms="on"),
        headers=bearer,
    )

    island_html = island.get_data(as_text=True)
    assert re.search(
        r'<label for="method-invoice" class="method-name">Invoice</label>', island_html
    )
    assert re.search(r"Total: €50\.00", island_html)
    assert re.search(
        r"<span>\s*symptoms\s*</span>\s*<span>\s*E2E test value\s*</span>", island_html
    )
    assert submitted.status_code == 200, submitted.get_data(as_text=True)
    invoice_id = CONFIRMATION.match(submitted.headers["HX-Redirect"]).group(1)
    invoice = client.get(
        f"/api/v1/user/invoices/{invoice_id}", headers=bearer
    ).get_json()
    invoice = invoice.get("invoice") or invoice
    assert invoice["status"] == "PENDING"
    assert invoice["invoice_number"].startswith("BK-")
    booking_line = invoice["line_items"][0]["metadata"]
    assert booking_line["resource_slug"] == resource["slug"]
    assert booking_line["custom_fields"] == {
        "symptoms": "E2E test value",
        "visits": 2,
        "insured": True,
    }
    assert booking_line["notes"] == "E2E test booking"

    paid = client.post(
        f"/api/v1/admin/invoices/{invoice_id}/mark-paid",
        json={"payment_reference": "S152-09", "payment_method": "invoice"},
        headers=admin_headers,
    )
    assert paid.status_code == 200, paid.get_json()
    success = regions_html(client, bearer, f"/booking-success?invoice_id={invoice_id}")
    assert re.search(r"<h1>\s*Booking Confirmed!\s*</h1>", success)
    assert re.search(rf'class="booking-resource-name">\s*{RESOURCE_NAME}\s*<', success)
    assert re.search(r'confirmation-label">\s*symptoms\s*<', success)
    assert re.search(r'confirmation-value">\s*E2E test booking\s*<', success)


@pytest.fixture
def stripe_sessions(monkeypatch):
    """Stubs the Stripe SDK at the outbound boundary only; records ``Session.create``."""
    created = []

    def create(**kwargs):
        created.append(kwargs)
        return SimpleNamespace(id="cs_test_booking", url=SESSION_URL)

    monkeypatch.setattr(stripe.checkout.Session, "create", create)
    return created


def test_the_stripe_method_goes_to_the_themed_stripe_page(
    client, bearer, resource, stripe_sessions
):
    pending = _pending_fields(client, resource)

    island_html = client.post(
        PAY_FORM, data=_pay_fields(pending), headers=bearer
    ).get_data(as_text=True)
    submitted = client.post(
        PAY_SUBMIT,
        data=_pay_fields(pending, payment_method="stripe", terms="on"),
        headers=bearer,
    )
    assert re.search(
        r'<label for="method-stripe" class="method-name">Pay with Stripe</label>',
        island_html,
    )
    assert submitted.status_code == 200, submitted.get_data(as_text=True)
    invoice_id = STRIPE_PAY.match(submitted.headers["HX-Redirect"]).group(1)

    pay_page = _page(client, f"/pay/stripe?invoice={invoice_id}")
    created = client.post(
        "/_render/_fragment/pay/stripe/create",
        data={"invoice_id": invoice_id},
        headers={**bearer, **ORIGIN},
    )

    assert '<meta name="vbwd-frontend" content="theme">' in pay_page
    assert created.status_code == 200, created.get_data(as_text=True)
    assert created.headers["HX-Redirect"] == SESSION_URL
    assert len(stripe_sessions) == 1
    assert stripe_sessions[0]["success_url"].startswith(
        "https://booking.example/pay/stripe/success"
    )


def test_a_refused_booking_shows_the_api_message(client, bearer, resource):
    pending = {**_pending_fields(client, resource), "end_at": "not-a-date"}

    submitted = client.post(
        PAY_SUBMIT,
        data=_pay_fields(pending, payment_method="invoice", terms="on"),
        headers=bearer,
    )

    html = submitted.get_data(as_text=True)
    assert "HX-Redirect" not in submitted.headers
    assert re.search(
        r'data-testid="checkout-form-error" class="error-message">\s*Invalid datetime format',
        html,
    )


def test_the_success_and_cancel_cms_pages_render_with_their_layout(client, resource):
    success = _page(client, "/booking-success")
    cancel = _page(client, "/booking-cancel")
    spa_success_route = _page(client, "/booking/success")

    assert re.search(r"<h1>\s*Payment Processing\s*</h1>", success)
    assert re.search(r"<h1>\s*Payment Cancelled\s*</h1>", cancel)
    assert re.search(r"(?s)<nav[^>]*>.*?<a ", spa_success_route)
    assert re.search(
        r'<div class="ghrm-error">\s*Resource not found\s*</div>', spa_success_route
    )


def test_a_disabled_fe_user_booking_plugin_404s_its_pages_and_fragments(
    client, resource, var_directory
):
    manifest = var_directory / "fe-user-plugins.json"
    write_manifest(manifest, [name for name in FE_USER_PLUGINS if name != "booking"])
    try:
        assert client.get("/booking", headers=RENDER).status_code == 404
        assert (
            client.get(
                f"/booking/{resource['slug']}/book/pay", headers=RENDER
            ).status_code
            == 404
        )
        assert client.post(PAY_FORM, data={"source": "booking"}).status_code == 404
    finally:
        write_manifest(manifest, FE_USER_PLUGINS)
