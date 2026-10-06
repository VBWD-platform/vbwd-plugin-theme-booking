"""Seeds the themed booking journey through the admin HTTP APIs (inside the rollback).

One active resource named like ``booking.spec.ts``'s (``E2E Playwright Resource``,
50.00, 30-minute slots Mon–Fri 09–17) with the three custom-field types the
specs fill, the booking CMS pages (each layout with a header menu, like the
seeded ``booking-*`` layouts) and the ``invoice`` + ``stripe`` payment methods.
"""
import uuid
from datetime import date, timedelta

from plugins.theme_checkout.tests.integration.themed_stack import (
    ensure_euro_currency,
    ensure_invoice_payment_method,
)

RESOURCE_NAME = "E2E Playwright Resource"
STRIPE_METHOD = {"code": "stripe", "name": "Pay with Stripe", "is_active": True}
WEEKDAY_HOURS = [{"start": "09:00", "end": "17:00"}]
CUSTOM_FIELDS_SCHEMA = [
    {"id": "symptoms", "label": "Symptoms", "type": "string", "required": True},
    {"id": "visits", "label": "Visits", "type": "integer", "required": False},
    {"id": "insured", "label": "Insured", "type": "boolean", "required": False},
]
CMS_PAGES = (
    ("booking", "BookingCatalogue"),
    ("booking-resource-detail", "BookingResourceDetail"),
    ("booking-form", "BookingForm"),
    ("booking-success", "BookingSuccess"),
    ("booking-cancel", "BookingCancel"),
)
MONDAY = 0


def next_monday() -> str:
    """``nextWeekday(MONDAY)``: the next Monday strictly after today."""
    today = date.today()
    return (today + timedelta(days=(MONDAY - today.weekday()) % 7 or 7)).isoformat()


def _ensure_stripe_method(client, admin_headers) -> None:
    methods = client.get("/api/v1/settings/payment-methods?currency=EUR").get_json()
    if any(method["code"] == "stripe" for method in methods.get("methods") or []):
        return
    created = client.post(
        "/api/v1/admin/payment-methods/", json=STRIPE_METHOD, headers=admin_headers
    )
    assert created.status_code == 201, created.get_json()


def _resource(client, admin_headers):
    created = client.post(
        "/api/v1/admin/booking/resources",
        json={
            "name": RESOURCE_NAME,
            "slug": f"s152-09-resource-{uuid.uuid4().hex[:8]}",
            "capacity": 5,
            "price": "50.00",
            "price_unit": "per_session",
            "slot_duration_minutes": 30,
            "is_active": True,
            "custom_fields_schema": CUSTOM_FIELDS_SCHEMA,
            "availability": {
                "schedule": {
                    **{
                        day: WEEKDAY_HOURS
                        for day in ("mon", "tue", "wed", "thu", "fri")
                    },
                    "sat": [],
                    "sun": [],
                }
            },
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.get_json()
    return created.get_json()


def _cms_page(cms, client, slug, component, menu):
    existing = client.get(f"/api/v1/cms/posts/{slug}")
    if existing.status_code == 200:
        return existing.get_json()
    return cms.page_with_widgets([menu, cms.vue_widget(component)], slug=slug)


def seed_booking_journey(client, admin_headers, cms):
    """The resource + CMS pages + payment methods; returns the resource payload."""
    ensure_euro_currency(client, admin_headers)
    ensure_invoice_payment_method(client, admin_headers)
    _ensure_stripe_method(client, admin_headers)
    menu = cms.widget("menu")
    cms.menu(
        menu["id"],
        [{"id": "a", "label": "Booking", "page_slug": "booking", "sort_order": 0}],
    )
    for slug, component in CMS_PAGES:
        _cms_page(cms, client, slug, component, menu)
    return _resource(client, admin_headers)
