"""The public booking API the fe-user plugin calls, always through core C2 (D3).

One method per ``/api/v1/booking/*`` endpoint the booking store and views use.
A facet ``options_endpoint`` is resolved by the shared catalogue helper, so the
absolute descriptor path is never double-prefixed.
"""
from typing import Any, Mapping
from urllib.parse import quote

from plugins.theme.theme.theme_api import call_api
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_cms.theme_cms.components.catalogue_filters import (
    API_PREFIX,
    options_api_path,
)

BOOKING_API_PREFIX = f"{API_PREFIX}/booking"


def _segment(value: str) -> str:
    return quote(value, safe="")


class BookingApi:
    """The booking endpoints for one themed request."""

    def __init__(self, theme_request: ThemeRequest) -> None:
        self._theme_request = theme_request

    def _get(self, path: str, **options: Any) -> Any:
        return call_api(self._theme_request, "GET", path, **options)

    def filters(self) -> Any:
        return self._get(f"{BOOKING_API_PREFIX}/filters")

    def options(self, endpoint: str) -> Any:
        return self._get(options_api_path(endpoint))

    def resources(self, query: Mapping[str, Any]) -> Any:
        return self._get(f"{BOOKING_API_PREFIX}/resources", query=dict(query))

    def resource(self, slug: str) -> Any:
        return self._get(f"{BOOKING_API_PREFIX}/resources/{_segment(slug)}")

    def availability(self, slug: str, date: str) -> Any:
        return self._get(
            f"{BOOKING_API_PREFIX}/resources/{_segment(slug)}/availability",
            query={"date": date},
        )

    def bookings(self) -> Any:
        """The viewer's bookings (first page, as the SPA asks)."""
        return self._get(f"{BOOKING_API_PREFIX}/bookings")

    def checkout(self, payload: Mapping[str, Any]) -> Any:
        return call_api(
            self._theme_request,
            "POST",
            f"{BOOKING_API_PREFIX}/checkout",
            json=dict(payload),
        )
