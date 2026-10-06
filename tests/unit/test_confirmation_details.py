"""S152-09b — BookingConfirmationDetails (``BookingConfirmationDetails.vue``) as a
``/checkout/confirmation`` section (theme_checkout's ``ConfirmationSectionRegistry``).

The SPA registers it as ``checkoutConfirmationRegistry.register('booking', …)``;
it shows for the invoice's first line item whose ``metadata.plugin`` is
``booking`` (the key the invoice API serialises — this component reads
``metadata`` correctly; only ``BookingSuccess.vue`` reads the never-sent
``extra_data``). Data: ``GET /booking/resources/<metadata.resource_slug>`` and
the viewer's ``GET /booking/bookings`` record for this invoice, else the line's
metadata (start, end, quantity, notes — no custom fields, as in the SPA). The
price prints the app default currency (``appConfig.defaultCurrency``, ``GET
/api/v1/config``). Any API refusal hides the section (the component's
``catch``). Template markup, classes and copy are pinned against the Vue file.
"""
import re
from pathlib import Path

import pytest

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_booking.tests.unit.fakes import RESOURCE, FakeBookingApi
from plugins.theme_booking.tests.unit.template_harness import render, theme_plugin
from plugins.theme_booking.theme_booking.confirmation_details import (
    BookingConfirmationDetails,
)
from plugins.theme_checkout.tests.unit.fakes import FakeCheckoutApi, FakeThemeRequest
from plugins.theme.tests.css_inventory import template_class_usage

TEMPLATE = "booking/confirmation_details.html.j2"
VUE_COMPONENT = (
    Path(__file__).resolve().parents[4].parent
    / "vbwd-fe-user"
    / "plugins"
    / "booking"
    / "booking"
    / "components"
    / "BookingConfirmationDetails.vue"
)
TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2] / "theme_booking" / "templates" / TEMPLATE
)
VUE_TEMPLATE_BLOCK = re.compile(r"<template>(.*)</template>", re.DOTALL)
VUE_CLASS = re.compile(r'\sclass="([^"]*)"')
VUE_TRANSLATION = re.compile(r"\$t\('([\w.]+)'\)")
JINJA_TRANSLATION = re.compile(r"_\('([\w.]+)'\)")
BOOKING_METADATA = {
    "plugin": "booking",
    "resource_slug": "dr-smith",
    "resource_name": "Dr. Smith",
    "start_at": "2026-11-02T09:00:00",
    "end_at": "2026-11-02T09:30:00",
    "quantity": 2,
    "custom_fields": {"symptoms": "From metadata"},
    "notes": "Metadata notes",
}
INVOICE = {
    "id": "inv-9",
    "line_items": [
        {"description": "Other", "metadata": {"plugin": "shop"}},
        {"description": "Dr. Smith", "metadata": BOOKING_METADATA},
    ],
}
BOOKING_RECORD = {
    "id": "b-1",
    "invoice_id": "inv-9",
    "start_at": "2026-11-02T10:00:00",
    "end_at": "2026-11-02T10:30:00",
    "quantity": 1,
    "custom_fields": {"symptoms": "Headache", "insured": True},
    "notes": "Record notes",
}

needs_fe_user = pytest.mark.skipif(
    not VUE_COMPONENT.is_file(), reason="the fe-user checkout is not next to backend"
)


def _details(api=None, invoice=INVOICE, user_id="user-a", checkout_api=None):
    api = api or FakeBookingApi(bookings={"bookings": [BOOKING_RECORD]})
    checkout_api = checkout_api or FakeCheckoutApi()
    theme_request = FakeThemeRequest(
        {"invoice_id": "inv-9"}, user_id=user_id, path="/checkout/confirmation"
    )
    details = BookingConfirmationDetails(api.factory, checkout_api.factory)
    return details.build_context(invoice, theme_request), api


# ── applies ──────────────────────────────────────────────────────────────────


def test_applies_to_an_invoice_with_a_booking_line_item():
    details = BookingConfirmationDetails()

    assert details.applies(INVOICE) is True


def test_does_not_apply_without_a_booking_line_item():
    details = BookingConfirmationDetails()

    assert details.applies({"line_items": [{"metadata": {"plugin": "shop"}}]}) is False
    assert details.applies({"line_items": []}) is False
    assert details.applies({}) is False


def test_extra_data_is_not_the_line_item_key_the_api_sends():
    details = BookingConfirmationDetails()

    assert details.applies({"line_items": [{"extra_data": BOOKING_METADATA}]}) is False


def test_the_section_is_booking_owned_by_fe_user_booking():
    section = BookingConfirmationDetails().section()

    assert section.name == "booking"
    assert section.owner_fe_user_plugin == "booking"
    assert section.template == TEMPLATE
    assert section.applies(INVOICE) is True


# ── build_context ────────────────────────────────────────────────────────────


def test_the_viewers_booking_record_for_this_invoice_fills_the_details():
    context, api = _details()

    assert api.called("resource") == [("resource", "dr-smith")]
    assert api.called("bookings") == [("bookings",)]
    assert context == {
        "resource": {
            "name": "Dr. Smith",
            "href": "/booking/dr-smith",
            "image_url": "/uploads/smith.png",
            "description": "General practice",
        },
        "price_line": "50.00 EUR/per_session",
        "date_time": "11/2/2026, 10:00:00 AM — 11/2/2026, 10:30:00 AM",
        "quantity": 1,
        "custom_fields": [("symptoms", "Headache"), ("insured", "true")],
        "notes": "Record notes",
    }


def test_without_a_matching_record_the_line_metadata_is_used_without_custom_fields():
    other_booking = {**BOOKING_RECORD, "invoice_id": "inv-other"}
    context, _api = _details(FakeBookingApi(bookings={"bookings": [other_booking]}))

    assert context["date_time"] == "11/2/2026, 9:00:00 AM — 11/2/2026, 9:30:00 AM"
    assert context["quantity"] == 2
    assert context["notes"] == "Metadata notes"
    assert context["custom_fields"] == []


def test_a_wrapped_resource_payload_is_unwrapped():
    context, _api = _details(
        FakeBookingApi(
            resource={"resource": {**RESOURCE, "name": "Wrapped"}},
            bookings={"bookings": []},
        )
    )

    assert context["resource"]["name"] == "Wrapped"


def test_the_price_line_prints_the_app_default_currency_not_the_resources():
    context, _api = _details(
        FakeBookingApi(
            resource={**RESOURCE, "currency": "GBP"}, bookings={"bookings": []}
        ),
        checkout_api=FakeCheckoutApi(default_currency="USD"),
    )

    assert context["price_line"] == "50.00 USD/per_session"


@pytest.mark.parametrize("price, shown", [(50.0, "50"), (49.5, "49.5"), (7, "7")])
def test_a_numeric_price_prints_as_javascript_prints_it(price, shown):
    """The API sends ``raw_price`` as a float; ``{{ 50.0 }}`` renders ``50``."""
    context, _api = _details(
        FakeBookingApi(resource={**RESOURCE, "price": price}, bookings={"bookings": []})
    )

    assert context["price_line"] == f"{shown} EUR/per_session"


@pytest.mark.parametrize(
    "refusal", [{"resource": ThemeApiError(404, "gone")}, {"bookings": None}]
)
def test_an_api_refusal_hides_the_section(refusal):
    context, _api = _details(
        FakeBookingApi(**{"bookings": {"bookings": []}, **refusal})
    )

    assert context is None


def test_a_refused_app_config_hides_the_section():
    context, _api = _details(
        checkout_api=FakeCheckoutApi(default_currency=ThemeApiError(503, "down"))
    )

    assert context is None


def test_a_line_without_a_resource_slug_hides_the_section_without_api_calls():
    invoice = {"line_items": [{"metadata": {"plugin": "booking"}}]}

    context, api = _details(invoice=invoice)

    assert context is None and api.calls == []


# ── template: BookingConfirmationDetails.vue's DOM and copy ──────────────────


@pytest.fixture(scope="module")
def plugin():
    return theme_plugin()


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def _html(plugin, context):
    return render(plugin, TEMPLATE, {"section": {"context": context}})


def test_the_section_markup_mirrors_the_vue_component(plugin):
    html = _html(plugin, _details()[0])

    assert re.search(r"^\s*<h2>\s*Resource Details\s*</h2>", html)
    assert re.search(
        r'<div class="booking-resource-block">\s*'
        r'<img src="/uploads/smith.png" alt="Dr. Smith" class="booking-resource-image">\s*'
        r'<div class="booking-resource-info">\s*'
        r'<a href="/booking/dr-smith" class="resource-name-link">\s*'
        r"<h3>\s*Dr. Smith\s*</h3>\s*</a>\s*"
        r'<p class="resource-description">\s*General practice\s*</p>',
        html,
    )
    assert re.search(
        r'<div class="booking-price-info">\s*'
        r'<span class="booking-price">\s*50.00 EUR/per_session\s*</span>',
        html,
    )
    assert re.search(r"<h3>\s*Booking &amp; Payment Details\s*</h3>", html)
    assert re.search(
        r'<div class="booking-details-grid">\s*<div class="detail-row">\s*'
        r'<span class="detail-label">\s*Date &amp; Time\s*</span>\s*'
        r'<span class="detail-value">\s*11/2/2026, 10:00:00 AM — 11/2/2026, 10:30:00 AM'
        r"\s*</span>\s*</div>\s*"
        r'<div class="detail-row">\s*<span class="detail-label">\s*Quantity\s*</span>\s*'
        r'<span class="detail-value">\s*1\s*</span>',
        html,
    )
    assert re.search(
        r'<div class="booking-custom-fields">\s*'
        r'<h3 class="section-label">\s*Additional information\s*</h3>\s*'
        r'<div class="detail-row">\s*<span class="detail-label">\s*symptoms\s*</span>\s*'
        r'<span class="detail-value">\s*Headache\s*</span>',
        html,
    )
    assert re.search(r'<span class="detail-value">\s*true\s*</span>', html)
    assert re.search(
        r'<div class="booking-notes">\s*<h3 class="section-label">\s*Notes\s*</h3>\s*'
        r"<p>\s*Record notes\s*</p>",
        html,
    )


def test_optional_parts_are_left_out_like_the_vue_v_ifs(plugin):
    context = {
        **_details()[0],
        "resource": {
            "name": "Dr. Smith",
            "href": "/booking/dr-smith",
            "image_url": None,
            "description": None,
        },
        "quantity": None,
        "custom_fields": [],
        "notes": None,
    }

    html = _html(plugin, context)

    for absent in (
        "booking-resource-image",
        "resource-description",
        "Quantity",
        "booking-custom-fields",
        "booking-notes",
    ):
        assert absent not in html, absent


def test_values_are_escaped(plugin):
    context = {**_details()[0], "notes": "<script>x</script>"}

    assert "&lt;script&gt;x&lt;/script&gt;" in _html(plugin, context)


@needs_fe_user
def test_the_template_uses_exactly_the_vue_components_classes():
    vue_template = VUE_TEMPLATE_BLOCK.search(
        VUE_COMPONENT.read_text(encoding="utf-8")
    ).group(1)
    vue_classes = {
        token
        for attribute in VUE_CLASS.findall(vue_template)
        for token in attribute.split()
    }
    theme_classes, _prefixes = template_class_usage([TEMPLATE_PATH])

    assert theme_classes == vue_classes


@needs_fe_user
def test_the_template_asks_for_exactly_the_vue_components_messages():
    vue_template = VUE_TEMPLATE_BLOCK.search(
        VUE_COMPONENT.read_text(encoding="utf-8")
    ).group(1)

    assert set(
        JINJA_TRANSLATION.findall(TEMPLATE_PATH.read_text(encoding="utf-8"))
    ) == set(VUE_TRANSLATION.findall(vue_template))
