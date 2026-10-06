"""The booking pay page's checkout source — the twin of ``BookingCheckout.vue`` (S152-09).

The SPA pays a booking on its own page (``/booking/<slug>/book/pay``), never
through ``/checkout``, so this :class:`CheckoutSource` lives in theme_booking's
own registry; theme_checkout's island and confirm fragments drive it, which
gives the pay page the shared email / billing / payment / terms blocks and the
post-submit dispatch (``handlePay``'s instantPay → redirectPath → confirmation).

The pending booking (the SPA's ``store.pendingCheckout``) arrives as the
``pending`` form field: the BookingForm fields ``booking_runtime.js`` kept in
``sessionStorage``. The resource's ``pricing`` block prices it (brutto, quantity
1 — the form sets no quantity), a coupon is validated in the ``BOOKING`` scope
and the submit is ``POST /api/v1/booking/checkout``.
"""
import json
from decimal import Decimal
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from plugins.theme.theme.theme_api import NOT_FOUND, ThemeApiError
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_api import CheckoutApi
from plugins.theme_checkout.theme_checkout.checkout_sources import (
    CheckoutRouteContext,
    CheckoutSource,
    CheckoutSummary,
)
from plugins.theme_checkout.theme_checkout.confirmation import locale_datetime
from plugins.theme_checkout.theme_checkout.coupon import price_coupon
from plugins.theme_checkout.theme_checkout.price_display import price_display_view

from .booking_api import BookingApi

BOOKING_SOURCE_ID = "booking"
PENDING_FIELD = "pending"
SUMMARY_TEMPLATE = "booking/pay_summary.html.j2"
COUPON_SCOPE = "BOOKING"
CUSTOM_FIELD_PREFIX = "custom_fields."
REQUIRED_PENDING_FIELDS = ("resource_slug", "start_at", "end_at")
BOOKING_NOT_FOUND = "Booking not found."
ZERO = Decimal("0")

ApiFactory = Callable[[ThemeRequest], Any]


def matches_booking(context: CheckoutRouteContext) -> bool:
    return context.source == BOOKING_SOURCE_ID


def posted_pending(form: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """The pending BookingForm fields, or ``None`` (absent, unreadable, incomplete)."""
    try:
        fields = json.loads(form.get(PENDING_FIELD) or "")
    except ValueError:
        return None
    if not isinstance(fields, dict):
        return None
    if not all(fields.get(name) for name in REQUIRED_PENDING_FIELDS):
        return None
    return fields


def _typed_value(field_type: Any, raw: Any) -> Tuple[bool, Any]:
    """``(present, value)`` as BookingForm's ``v-model`` would hold it."""
    if field_type == "integer":
        try:
            return True, int(raw)
        except (TypeError, ValueError):
            return False, None
    if field_type == "boolean":
        return bool(raw), True
    return bool(raw), raw


def booking_payload(
    fields: Mapping[str, Any], schema: List[Mapping[str, Any]]
) -> Dict[str, Any]:
    """The ``POST /booking/checkout`` body (``handleSubmit``'s pendingCheckout)."""
    custom_fields: Dict[str, Any] = {}
    for field in schema:
        present, value = _typed_value(
            field.get("type"), fields.get(f"{CUSTOM_FIELD_PREFIX}{field.get('id')}")
        )
        if present:
            custom_fields[str(field.get("id"))] = value
    payload: Dict[str, Any] = {name: fields[name] for name in REQUIRED_PENDING_FIELDS}
    payload["custom_fields"] = custom_fields
    if fields.get("notes"):
        payload["notes"] = fields["notes"]
    return payload


def display_value(value: Any) -> str:
    """Vue's ``{{ value }}``: booleans print lower-case."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _unit_amounts(resource: Mapping[str, Any]) -> Tuple[Any, Any]:
    pricing = resource.get("pricing") or {}
    price = resource.get("price") or ZERO
    net = pricing.get("net_amount")
    gross = pricing.get("gross_amount")
    return (price if net is None else net), (price if gross is None else gross)


class BookingCheckout:
    """Prices and submits the pending booking of one pay-page request."""

    def __init__(
        self,
        api_factory: ApiFactory = BookingApi,
        checkout_api_factory: ApiFactory = CheckoutApi,
    ) -> None:
        self._api_factory = api_factory
        self._checkout_api_factory = checkout_api_factory

    def checkout_source(self) -> CheckoutSource:
        return CheckoutSource(
            id=BOOKING_SOURCE_ID,
            matches=matches_booking,
            load_summary=self.load_summary,
            submit=self.submit,
            summary_template=SUMMARY_TEMPLATE,
            cart_key=None,
        )

    def _pending_booking(
        self, theme_request: ThemeRequest
    ) -> Tuple[Mapping[str, Any], Mapping[str, Any]]:
        """``(pending fields, resource)``; raises ``ThemeApiError`` when either is missing."""
        fields = posted_pending(theme_request.query_args)
        if fields is None:
            raise ThemeApiError(NOT_FOUND, BOOKING_NOT_FOUND)
        resource = self._api_factory(theme_request).resource(fields["resource_slug"])
        return fields, resource

    def load_summary(
        self, theme_request: ThemeRequest, context: CheckoutRouteContext
    ) -> CheckoutSummary:
        fields, resource = self._pending_booking(theme_request)
        checkout_api = self._checkout_api_factory(theme_request)
        currency = checkout_api.default_currency()
        net, gross = _unit_amounts(resource)
        gross_total = Decimal(str(gross))
        coupon = price_coupon(
            checkout_api, context.coupon_code, gross_total, COUPON_SCOPE
        )
        payload = booking_payload(fields, resource.get("custom_fields_schema") or [])
        pricing = resource.get("pricing") or {}
        return CheckoutSummary(
            line_items=(
                {
                    "type": BOOKING_SOURCE_ID,
                    "id": resource.get("id"),
                    "name": resource.get("name"),
                    "price": float(gross_total),
                    "quantity": 1,
                    "currency": currency,
                },
            ),
            order_total=max(ZERO, gross_total - coupon.discount_amount),
            currency=currency,
            discount_amount=coupon.discount_amount,
            applied_coupon_code=coupon.applied_code,
            coupon_error=coupon.error,
            template_context={
                "resource": {
                    "name": resource.get("name") or "",
                    "href": f"/booking/{resource.get('slug')}",
                    "image_url": resource.get("image_url"),
                    "resource_type": resource.get("resource_type") or "",
                    "description": resource.get("description"),
                    "price": price_display_view(
                        net,
                        gross,
                        currency,
                        pricing.get("effective_display_mode"),
                        pricing.get("prices_display_mode"),
                    ),
                },
                "date_time": (
                    f"{locale_datetime(payload['start_at'])} — "
                    f"{locale_datetime(payload['end_at'])}"
                ),
                "notes": payload.get("notes"),
                "custom_fields": [
                    (key, display_value(value))
                    for key, value in payload["custom_fields"].items()
                ],
            },
        )

    def submit(
        self,
        theme_request: ThemeRequest,
        context: CheckoutRouteContext,
        payment_method_code: Optional[str],
    ) -> Mapping[str, Any]:
        fields, resource = self._pending_booking(theme_request)
        payload = booking_payload(fields, resource.get("custom_fields_schema") or [])
        if context.coupon_code:
            payload["coupon_code"] = context.coupon_code
        response = self._api_factory(theme_request).checkout(payload)
        return {
            "invoice": {
                "id": response.get("invoice_id"),
                "invoice_number": response.get("invoice_number"),
            }
        }
