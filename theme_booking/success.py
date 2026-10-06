"""BookingSuccess — the twin of ``BookingSuccess.vue`` (CMS page ``booking-success``).

Rendered inside a CMS layout area, i.e. a personalised region (D12): the
anonymous page shows the pending banner without an API call; the viewer's
re-render reads ``GET /api/v1/user/invoices/<id>`` with the bearer (the API
scopes by owner). The booking line item is the one whose ``metadata.plugin`` is
``booking`` — the key the invoice API serialises (``InvoiceLineItem.to_dict``);
the SPA reads ``extra_data``, which the API never sends. The amount row is the
totals-level ``PriceBreakdown`` from the persisted invoice fields.
"""
from decimal import Decimal
from typing import Any, Callable, Dict, Mapping, Optional

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_api import CheckoutApi
from plugins.theme_checkout.theme_checkout.confirmation import locale_datetime
from plugins.theme_cms.theme_cms.components.pricing import format_money

from .booking_api import BookingApi
from .checkout_source import BOOKING_SOURCE_ID, display_value

INVOICE_ID_PARAMETERS = ("invoice_id", "invoice")
PENDING_STATUS = "pending"
PAID_STATUS = "paid"
AUTHORIZED_STATUS = "authorized"
TITLE_KEYS = {
    PAID_STATUS: "booking.success.titlePaid",
    AUTHORIZED_STATUS: "booking.success.titleAuthorized",
}
DEFAULT_TITLE_KEY = "booking.success.titlePending"
MESSAGE_PAID_KEY = "booking.success.messagePaid"
MESSAGE_PENDING_KEY = "booking.success.messagePending"
# BookingSuccess.vue's single aggregate tax line (no per-rate split on the invoice).
AGGREGATE_TAX_CODE = "TAX"
AGGREGATE_TAX_RATE = 0
ZERO = Decimal("0")

ApiFactory = Callable[[ThemeRequest], Any]


def _present(value: Any, fallback: Any) -> Any:
    return fallback if value is None else value


def _breakdown(invoice: Mapping[str, Any], currency: str) -> Dict[str, Any]:
    """``invoiceBreakdownPrice``: netto = subtotal, brutto = total, one tax line."""
    gross = Decimal(str(_present(invoice.get("total_amount"), invoice.get("amount"))))
    net = Decimal(str(_present(invoice.get("subtotal"), gross)))
    tax = Decimal(str(_present(invoice.get("tax_amount"), ZERO)))
    taxes = (
        [
            {
                "label_name": AGGREGATE_TAX_CODE,
                "rate": AGGREGATE_TAX_RATE,
                "amount": format_money(tax, currency),
            }
        ]
        if tax > ZERO
        else []
    )
    return {
        "net": format_money(net, currency),
        "taxes": taxes,
        "gross": format_money(gross, currency),
    }


def booking_line_metadata(invoice: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
    """The first line item's ``metadata`` whose ``plugin`` is ``booking`` (else ``None``)."""
    return next(
        (
            item.get("metadata") or {}
            for item in invoice.get("line_items") or []
            if (item.get("metadata") or {}).get("plugin") == BOOKING_SOURCE_ID
        ),
        None,
    )


class BookingSuccess:
    """``build_context(widget_config, page, route_params, theme_request)``."""

    def __init__(
        self,
        api_factory: ApiFactory = BookingApi,
        checkout_api_factory: ApiFactory = CheckoutApi,
    ) -> None:
        self._api_factory = api_factory
        self._checkout_api_factory = checkout_api_factory

    def build_context(
        self,
        widget_config: Mapping[str, Any],
        page: Mapping[str, Any],
        route_params: Mapping[str, Any],
        theme_request: ThemeRequest,
    ) -> Dict[str, Any]:
        invoice = self._read_invoice(theme_request)
        status = str((invoice or {}).get("status") or PENDING_STATUS).lower()
        return {
            "status": status,
            "title_key": TITLE_KEYS.get(status, DEFAULT_TITLE_KEY),
            "message_key": MESSAGE_PAID_KEY
            if status == PAID_STATUS
            else MESSAGE_PENDING_KEY,
            "invoice": self._invoice_view(theme_request, invoice) if invoice else None,
            "booking": self._booking_view(theme_request, invoice) if invoice else None,
        }

    def _read_invoice(self, theme_request: ThemeRequest) -> Optional[Mapping[str, Any]]:
        query = theme_request.query_args
        invoice_id = next(
            (query[name] for name in INVOICE_ID_PARAMETERS if query.get(name)), ""
        )
        if not invoice_id or theme_request.viewer.user_id is None:
            return None
        try:
            response = self._checkout_api_factory(theme_request).invoice(invoice_id)
        except ThemeApiError:
            return None
        invoice: Mapping[str, Any] = response.get("invoice") or response
        return invoice

    def _invoice_view(
        self, theme_request: ThemeRequest, invoice: Mapping[str, Any]
    ) -> Dict[str, Any]:
        currency = (
            invoice.get("currency")
            or self._checkout_api_factory(theme_request).default_currency()
        )
        return {
            "number": invoice.get("invoice_number") or "",
            "breakdown": _breakdown(invoice, currency)
            if invoice.get("amount")
            else None,
            "paid_at": locale_datetime(invoice.get("paid_at")),
        }

    def _booking_view(
        self, theme_request: ThemeRequest, invoice: Mapping[str, Any]
    ) -> Optional[Dict[str, Any]]:
        line = booking_line_metadata(invoice)
        if line is None:
            return None
        slug = line.get("resource_slug") or ""
        try:
            resource = self._api_factory(theme_request).resource(slug)
        except ThemeApiError:
            resource = {
                "name": line.get("resource_name"),
                "slug": slug,
                "resource_type": line.get("resource_type"),
            }
        return {
            "resource": {
                "name": resource.get("name") or "",
                "href": f"/booking/{slug}",
                "image_url": resource.get("image_url"),
                "resource_type": resource.get("resource_type") or "",
                "description": resource.get("description"),
            },
            "date_time": (
                f"{locale_datetime(line.get('start_at'))} — "
                f"{locale_datetime(line.get('end_at'))}"
            )
            if line.get("start_at")
            else "",
            "custom_fields": [
                (key, display_value(value))
                for key, value in (line.get("custom_fields") or {}).items()
            ],
            "notes": line.get("notes"),
        }
