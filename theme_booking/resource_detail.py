"""BookingResourceDetail — the twin of ``BookingResourceDetail.vue`` — and its slot picker.

The price is in the app default currency (``appConfig.defaultCurrency``, read
from ``GET /api/v1/config`` by theme_checkout's ``CheckoutApi``). The resource
comes from the route slug (``/booking/<slug>`` renders the CMS page
``booking-resource-detail``). A fixed-slot resource picks a date; its slots are
the ``/_render/_fragment/booking/slots`` fragment over the same availability
call as the SPA. A flexible resource (no slot duration) picks check-in and
check-out. "Book Now" submits a GET form to ``/<bookingFormSlug>/<slug>`` with
the SPA's query (``date`` + ``start`` / ``end``, or ``end_date``).
"""
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, List, Mapping

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_api import CheckoutApi
from plugins.theme_cms.theme_cms.tags_custom_fields import tags_and_custom_fields

from .booking_api import BookingApi
from .catalogue import price_unit, resource_price

SLOTS_FRAGMENT_PATH = "/_render/_fragment/booking/slots"
ISO_TIME_SEPARATOR = "T"
CLOCK_TIME = slice(11, 16)

ApiFactory = Callable[[ThemeRequest], Any]


def utc_today() -> date:
    """``new Date().toISOString().split('T')[0]`` — the SPA's ``todayString``."""
    return datetime.now(timezone.utc).date()


def is_flexible(resource: Mapping[str, Any]) -> bool:
    """A resource without a slot duration books whole days (``isFlexibleDuration``)."""
    return resource.get("slot_duration_minutes") is None


def slot_clock_time(value: str) -> str:
    """``slotClockTime``: a slot boundary (``09:00`` or an ISO datetime) as ``HH:MM``."""
    return value[CLOCK_TIME] if ISO_TIME_SEPARATOR in value else value


def format_slot_time(slot: Mapping[str, Any]) -> str:
    """``formatSlotTime``: ``start – end`` (an ISO time is cut to HH:MM), else the date."""
    if slot.get("start") and slot.get("end"):
        return f"{slot_clock_time(slot['start'])} – {slot_clock_time(slot['end'])}"
    return str(slot.get("date") or "")


def _resource_view(resource: Mapping[str, Any], currency: str) -> Dict[str, Any]:
    images = [
        {"url": image.get("url") or "", "alt": image.get("alt") or ""}
        for image in resource.get("images") or []
    ]
    return {
        "name": resource.get("name") or "",
        "resource_type": resource.get("resource_type") or "",
        "description": resource.get("description"),
        "price": resource_price(resource, currency),
        "price_unit": price_unit(resource),
        "capacity": int(resource.get("capacity") or 0),
        "categories": [
            category.get("name") or "" for category in resource.get("categories") or []
        ],
        "images": images,
        "active_image_url": resource.get("image_url") or "",
        "image_url": resource.get("image_url"),
        "show_header_icon": not images and bool(resource.get("image_url")),
        "tags_custom_fields": tags_and_custom_fields(resource),
    }


class BookingResourceDetail:
    """``build_context(widget_config, page, route_params, theme_request)``."""

    def __init__(
        self,
        booking_form_slug: str,
        api_factory: ApiFactory = BookingApi,
        checkout_api_factory: ApiFactory = CheckoutApi,
        today: Callable[[], date] = utc_today,
    ) -> None:
        self._booking_form_slug = booking_form_slug
        self._api_factory = api_factory
        self._checkout_api_factory = checkout_api_factory
        self._today = today

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
        return {
            "state": "resource",
            "slug": slug,
            "resource": _resource_view(resource, currency),
            "is_flexible": is_flexible(resource),
            "today": self._today().isoformat(),
            "form_action": f"/{self._booking_form_slug}/{slug}",
            "slots_url": SLOTS_FRAGMENT_PATH,
        }


class SlotPicker:
    """The slots fragment: one day's availability of one resource."""

    def __init__(self, api_factory: ApiFactory = BookingApi) -> None:
        self._api_factory = api_factory

    def fragment_context(self, theme_request: ThemeRequest) -> Dict[str, Any]:
        picked_date = theme_request.query_args.get("date") or ""
        if not picked_date:
            return {"state": "pick_date", "slots": []}
        resource_slug = theme_request.query_args.get("resource") or ""
        try:
            answer = self._api_factory(theme_request).availability(
                resource_slug, picked_date
            )
        except ThemeApiError:
            return {"state": "no_slots", "slots": []}
        slots: List[Dict[str, Any]] = [
            {
                "label": format_slot_time(slot),
                "capacity": int(slot.get("available_capacity") or 0),
                "full": int(slot.get("available_capacity") or 0) == 0,
                "start": slot.get("start") or "",
                "end": slot.get("end") or "",
            }
            for slot in answer.get("slots") or []
        ]
        return {"state": "slots" if slots else "no_slots", "slots": slots}
