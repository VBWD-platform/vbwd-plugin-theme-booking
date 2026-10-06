"""S152-09 — the public booking endpoints, always through core C2 (D3).

The same calls the fe-user booking store and views make: filters, the facet
options (absolute ``options_endpoint`` kept, never double-prefixed — cf.
BookingCatalogue.vue's ``.replace('/api/v1', '')``), the catalogue list, one
resource, a day's availability and ``POST /booking/checkout``.
"""
import pytest

from plugins.theme_booking.theme_booking import booking_api
from plugins.theme_booking.theme_booking.booking_api import BookingApi
from plugins.theme_checkout.tests.unit.fakes import FakeThemeRequest, ScriptedApi


@pytest.fixture
def scripted(monkeypatch):
    api = ScriptedApi(
        {
            ("GET", "/api/v1/booking/filters"): {"facets": []},
            ("GET", "/api/v1/booking/tags"): {"tags": []},
            ("GET", "/api/v1/booking/resources"): {"items": []},
            ("GET", "/api/v1/booking/resources/dr%20smith"): {"slug": "dr smith"},
            ("GET", "/api/v1/booking/resources/dr-smith/availability"): {"slots": []},
            ("POST", "/api/v1/booking/checkout"): {"invoice_id": "i"},
        }
    )
    monkeypatch.setattr(booking_api, "call_api", api)
    return api


def test_each_method_calls_the_endpoint_the_spa_calls(scripted):
    api = BookingApi(FakeThemeRequest())

    api.filters()
    api.options("/api/v1/booking/tags")
    api.resources({"page": 1, "per_page": 12})
    api.resource("dr smith")
    api.availability("dr-smith", "2026-11-02")
    api.checkout({"resource_slug": "dr-smith"})

    assert scripted.paths() == [
        ("GET", "/api/v1/booking/filters"),
        ("GET", "/api/v1/booking/tags"),
        ("GET", "/api/v1/booking/resources"),
        ("GET", "/api/v1/booking/resources/dr%20smith"),
        ("GET", "/api/v1/booking/resources/dr-smith/availability"),
        ("POST", "/api/v1/booking/checkout"),
    ]
    assert scripted.calls[2][2] == {"query": {"page": 1, "per_page": 12}}
    assert scripted.calls[4][2] == {"query": {"date": "2026-11-02"}}
    assert scripted.calls[5][2] == {"json": {"resource_slug": "dr-smith"}}
