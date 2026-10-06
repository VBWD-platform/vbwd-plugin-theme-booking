"""S152-09b — BookingConfirmationDetails on the themed ``/checkout/confirmation``.

A real ``create_app`` (theme mode) over the REAL booking, checkout and cms
plugins: a themed booking paid by invoice redirects to the confirmation page,
whose CheckoutConfirmation region (bearer re-render) carries theme_booking's
confirmation section for the invoice's owner — from the line metadata while the
invoice is pending, from the booking record (with its custom fields) once paid.
Another user on the same URL sees neither the invoice nor the booking (GDPR); a
non-booking invoice and a disabled fe-user booking plugin get no section.
"""
import re
from decimal import Decimal

import pytest

from plugins.theme_booking.tests.integration.booking_seed import (
    RESOURCE_NAME,
    seed_booking_journey,
)
from plugins.theme_booking.tests.integration.conftest import FE_USER_PLUGINS
from plugins.theme_booking.tests.integration.test_booking_flow import (
    CONFIRMATION,
    PAY_SUBMIT,
    _pay_fields,
    _pending_fields,
)
from plugins.theme_checkout.tests.integration.themed_stack import (
    TEST_USER,
    confirmation_page,
    regions_html,
)
from plugins.theme_checkout.tests.integration.payment.conftest import write_manifest

BOOKING_SECTION = '<div class="card" data-confirmation-section="booking">'
INVOICE_DETAILS = 'data-testid="invoice-details"'


@pytest.fixture
def resource(client, admin_headers, cms):
    confirmation_page(cms, client)
    return seed_booking_journey(client, admin_headers, cms)


@pytest.fixture
def booking_invoice_id(client, bearer, resource):
    pending = _pending_fields(client, resource)
    submitted = client.post(
        PAY_SUBMIT,
        data=_pay_fields(pending, payment_method="invoice", terms="on"),
        headers=bearer,
    )
    assert submitted.status_code == 200, submitted.get_data(as_text=True)
    return CONFIRMATION.match(submitted.headers["HX-Redirect"]).group(1)


def _confirmation(client, headers, invoice_id):
    return regions_html(
        client, headers, f"/checkout/confirmation?invoice_id={invoice_id}"
    )


def test_the_owner_sees_the_booking_section_from_the_pending_line(
    client, bearer, resource, booking_invoice_id
):
    html = _confirmation(client, bearer, booking_invoice_id)

    assert html.index(INVOICE_DETAILS) < html.index(BOOKING_SECTION)
    section = html[html.index(BOOKING_SECTION) :]
    assert re.search(r"<h2>\s*Resource Details\s*</h2>", section)
    assert re.search(
        rf'<a href="/booking/{resource["slug"]}" class="resource-name-link">\s*'
        rf"<h3>\s*{RESOURCE_NAME}\s*</h3>",
        section,
    )
    # The API's float ``price`` prints as JavaScript prints it (``50``).
    assert re.search(r'<span class="booking-price">\s*50 EUR/per_session\s*<', section)
    assert re.search(
        r'<span class="detail-value">\s*\d+/\d+/\d{4}, 9:00:00 AM', section
    )
    assert re.search(r"<p>\s*E2E test booking\s*</p>", section)
    # The SPA's metadata fallback carries no custom fields.
    assert "booking-custom-fields" not in section


def test_once_paid_the_booking_record_brings_its_custom_fields(
    client, bearer, admin_headers, booking_invoice_id
):
    paid = client.post(
        f"/api/v1/admin/invoices/{booking_invoice_id}/mark-paid",
        json={"payment_reference": "S152-09b", "payment_method": "invoice"},
        headers=admin_headers,
    )
    assert paid.status_code == 200, paid.get_json()

    section = _confirmation(client, bearer, booking_invoice_id)
    section = section[section.index(BOOKING_SECTION) :]

    assert re.search(
        r'<h3 class="section-label">\s*Additional information\s*</h3>', section
    )
    assert re.search(
        r'<span class="detail-label">\s*symptoms\s*</span>\s*'
        r'<span class="detail-value">\s*E2E test value\s*</span>',
        section,
    )


def test_another_user_sees_neither_the_invoice_nor_the_booking(
    client, admin_headers, booking_invoice_id
):
    html = _confirmation(client, admin_headers, booking_invoice_id)

    assert re.search(r"<h1>\s*Payment Processing\s*</h1>", html)
    assert INVOICE_DETAILS not in html
    assert "data-confirmation-section" not in html
    assert RESOURCE_NAME not in html


def test_a_non_booking_invoice_has_no_booking_section(client, bearer, db, resource):
    from vbwd.repositories.invoice_repository import InvoiceRepository
    from vbwd.repositories.user_repository import UserRepository
    from vbwd.services.invoice_service import InvoiceService

    test_user = UserRepository(db.session).find_by_email(TEST_USER["email"])
    created = InvoiceService(InvoiceRepository(db.session)).create_invoice(
        str(test_user.id), Decimal("12.00")
    )
    assert created.success, created.error

    html = _confirmation(client, bearer, created.invoice.id)

    assert INVOICE_DETAILS in html
    assert "data-confirmation-section" not in html


def test_a_disabled_fe_user_booking_plugin_drops_the_section(
    client, bearer, booking_invoice_id, var_directory
):
    manifest = var_directory / "fe-user-plugins.json"
    write_manifest(manifest, [name for name in FE_USER_PLUGINS if name != "booking"])
    try:
        html = _confirmation(client, bearer, booking_invoice_id)
    finally:
        write_manifest(manifest, FE_USER_PLUGINS)

    assert INVOICE_DETAILS in html
    assert "data-confirmation-section" not in html
