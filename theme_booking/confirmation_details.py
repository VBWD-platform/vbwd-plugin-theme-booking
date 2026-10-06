"""BookingConfirmationDetails — the twin of ``BookingConfirmationDetails.vue``.

A section of theme_checkout's ``/checkout/confirmation`` (its
``ConfirmationSectionRegistry``, as the SPA's ``checkoutConfirmationRegistry``).
It applies to an invoice with a booking line item (``metadata.plugin ==
"booking"`` — the key the invoice API serialises, and the one this Vue component
reads). Like the component it reads the resource and the viewer's booking for
this invoice, falling back to the line's metadata (no custom fields there, as in
the SPA); the price prints the app default currency (``GET /api/v1/config``
through theme_checkout's ``CheckoutApi``); any API refusal hides the section.
It renders inside the confirmation region's re-render, so every call carries
the owner's bearer.
"""
from typing import Any, Callable, Dict, Mapping, Optional

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_api import CheckoutApi
from plugins.theme_checkout.theme_checkout.confirmation import locale_datetime
from plugins.theme_checkout.theme_checkout.confirmation_sections import (
    ConfirmationSection,
)

from .booking_api import BookingApi
from .checkout_source import display_value
from .success import booking_line_metadata

# ``checkoutConfirmationRegistry.register('booking', …)`` in fe-user booking/index.ts.
CONFIRMATION_SECTION_NAME = "booking"
BOOKING_FE_USER_PLUGIN = "booking"
TEMPLATE = "booking/confirmation_details.html.j2"
FALLBACK_FIELDS = ("start_at", "end_at", "quantity", "notes")


def _text(value: Any) -> str:
    """Vue's ``{{ value }}``: ``null`` prints nothing, a whole float as an integer."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _price_line(resource: Mapping[str, Any], currency: str) -> str:
    """``{{ resource.price }} {{ appConfig.defaultCurrency }}/{{ resource.price_unit }}``."""
    return (
        f"{_text(resource.get('price'))} {currency}"
        f"/{_text(resource.get('price_unit'))}"
    )


class BookingConfirmationDetails:
    """``applies(invoice)`` + ``build_context(invoice, theme_request)`` of the section."""

    def __init__(
        self,
        api_factory: Callable[[ThemeRequest], Any] = BookingApi,
        checkout_api_factory: Callable[[ThemeRequest], Any] = CheckoutApi,
    ) -> None:
        self._api_factory = api_factory
        self._checkout_api_factory = checkout_api_factory

    def section(self) -> ConfirmationSection:
        return ConfirmationSection(
            name=CONFIRMATION_SECTION_NAME,
            owner_fe_user_plugin=BOOKING_FE_USER_PLUGIN,
            applies=self.applies,
            template=TEMPLATE,
            build_context=self.build_context,
        )

    def applies(self, invoice: Mapping[str, Any]) -> bool:
        return booking_line_metadata(invoice) is not None

    def build_context(
        self, invoice: Mapping[str, Any], theme_request: ThemeRequest
    ) -> Optional[Dict[str, Any]]:
        metadata = booking_line_metadata(invoice) or {}
        slug = metadata.get("resource_slug")
        if not slug:
            return None
        api = self._api_factory(theme_request)
        try:
            resource_response = api.resource(slug)
            bookings = api.bookings().get("bookings") or []
            currency = self._checkout_api_factory(theme_request).default_currency()
        except ThemeApiError:
            return None
        resource = resource_response.get("resource") or resource_response
        booking = next(
            (
                record
                for record in bookings
                if str(record.get("invoice_id")) == str(invoice.get("id"))
            ),
            None,
        ) or {field: metadata.get(field) for field in FALLBACK_FIELDS}
        return {
            "resource": {
                "name": resource.get("name") or "",
                "href": f"/booking/{resource.get('slug') or slug}",
                "image_url": resource.get("image_url"),
                "description": resource.get("description"),
            },
            "price_line": _price_line(resource, currency),
            "date_time": f"{locale_datetime(booking.get('start_at'))} — "
            f"{locale_datetime(booking.get('end_at'))}",
            "quantity": booking.get("quantity"),
            "custom_fields": [
                (key, display_value(value))
                for key, value in (booking.get("custom_fields") or {}).items()
            ],
            "notes": booking.get("notes"),
        }
