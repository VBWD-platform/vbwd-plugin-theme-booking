"""BookingForm — the twin of ``BookingForm.vue`` (the CMS page ``<bookingFormSlug>``).

The slot rides in the query from the detail page; ``start_at`` / ``end_at`` are
built as the SPA builds them (a boundary that arrives as an ISO datetime is cut
to its clock time, ``slotClockTime``). The header prints the app default
currency (``GET /api/v1/config`` through theme_checkout's ``CheckoutApi``).
Each ``custom_fields_schema`` field gets the SPA's input. The SPA keeps the
filled form in its store until the pay page reads it; here
``booking_runtime.js`` keeps it in ``sessionStorage`` (never the URL — the
notes and fields may be personal) and posts it with each pay-island request.
"""
from typing import Any, Callable, Dict, Mapping, Optional

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_api import CheckoutApi

from .booking_api import BookingApi
from .catalogue import price_unit
from .resource_detail import is_flexible, slot_clock_time

# custom_fields_schema ``type`` → the input BookingForm.vue renders (else a bare label).
FIELD_INPUTS = {
    "string": "text",
    "text": "text",
    "integer": "number",
    "boolean": "checkbox",
}
FLEXIBLE_CHECK_IN_TIME = "14:00:00"
FLEXIBLE_CHECK_OUT_TIME = "11:00:00"
SECONDS_SUFFIX = ":00"

ApiFactory = Callable[[ThemeRequest], Any]


def _slot_times(query: Mapping[str, Any], flexible: bool) -> Dict[str, str]:
    """``displayDateTime`` + ``buildStartAt`` / ``buildEndAt``."""
    picked_date = query.get("date") or ""
    if flexible:
        end_date = query.get("end_date") or ""
        return {
            "display_date_time": f"{picked_date} → {end_date}",
            "start_at": f"{picked_date}T{FLEXIBLE_CHECK_IN_TIME}",
            "end_at": f"{end_date}T{FLEXIBLE_CHECK_OUT_TIME}",
        }
    start = slot_clock_time(query.get("start") or "")
    end = slot_clock_time(query.get("end") or "")
    return {
        "display_date_time": f"{picked_date}  {start} – {end}",
        "start_at": f"{picked_date}T{start}{SECONDS_SUFFIX}",
        "end_at": f"{picked_date}T{end}{SECONDS_SUFFIX}",
    }


def _field_view(field: Mapping[str, Any]) -> Dict[str, Any]:
    input_kind: Optional[str] = FIELD_INPUTS.get(str(field.get("type")))
    return {
        "id": field.get("id"),
        "label": field.get("label") or "",
        "required": bool(field.get("required")),
        "input": input_kind,
    }


class BookingForm:
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
        slug = str(route_params.get("slug") or "")
        try:
            resource = self._api_factory(theme_request).resource(slug)
        except ThemeApiError:
            return {"state": "not_found"}
        currency = self._checkout_api_factory(theme_request).default_currency()
        summary_line = (
            f"{resource.get('resource_type') or ''} · {resource.get('price') or ''} "
            f"{currency} / {price_unit(resource)}"
        )
        return {
            "state": "resource",
            "resource_slug": slug,
            "resource": {
                "name": resource.get("name") or "",
                "image_url": resource.get("image_url"),
                "summary_line": summary_line,
            },
            **_slot_times(theme_request.query_args, is_flexible(resource)),
            "custom_fields": [
                _field_view(field)
                for field in resource.get("custom_fields_schema") or []
            ],
            "pay_path": f"/booking/{slug}/book/pay",
            "back_href": f"/booking/{slug}",
        }
