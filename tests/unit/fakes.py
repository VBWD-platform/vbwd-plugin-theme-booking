"""Test doubles for the theme_booking unit tests: a scripted ``BookingApi`` + payloads."""
from plugins.theme.theme.theme_api import ThemeApiError

FACETS = {
    "facets": [
        {
            "key": "type",
            "label": "Type",
            "control": "select",
            "options_endpoint": "/api/v1/booking/schemas",
        },
        {
            "key": "tags",
            "label": "Tags",
            "control": "chips",
            "options_endpoint": "/api/v1/booking/tags",
        },
        {"key": "availability", "label": "Availability", "control": "date-range"},
    ]
}
SCHEMAS = {"schemas": [{"slug": "specialist", "name": "Specialist"}]}
TAGS = {"tags": [{"slug": "quiet", "name": "Quiet"}]}
RESOURCE_CARD = {
    "id": "r-1",
    "slug": "dr-smith",
    "name": "Dr. Smith",
    "description": "General practice",
    "resource_type": "specialist",
    "capacity": 3,
    "slot_duration_minutes": 30,
    "price": "50.00",
    "price_unit": "per_session",
    "image_url": "/uploads/smith.png",
    "tags": ["quiet"],
    "pricing": {
        "net_amount": "42.02",
        "gross_amount": "50.00",
        "effective_display_mode": "brutto",
        "prices_display_mode": "brutto",
        "taxes": [{"code": "VAT", "name": "VAT", "rate": "19", "amount": "7.98"}],
    },
}
RESOURCE = {
    **RESOURCE_CARD,
    "images": [
        {"id": "i-1", "url": "/uploads/smith.png", "alt": "front", "is_primary": True},
        {"id": "i-2", "url": "/uploads/room.png", "alt": "", "is_primary": False},
    ],
    "categories": [{"id": "c-1", "name": "Health", "slug": "health"}],
    "custom_fields_schema": [
        {"id": "symptoms", "label": "Symptoms", "type": "string", "required": True},
        {"id": "visits", "label": "Visits", "type": "integer", "required": False},
        {"id": "insured", "label": "Insured", "type": "boolean", "required": False},
    ],
    "tags": [],
    "custom_fields": {},
    "custom_field_defs": [],
}
FLEXIBLE_RESOURCE = {**RESOURCE, "slug": "seaside-room", "slot_duration_minutes": None}
SLOTS = {
    "date": "2026-11-02",
    "slots": [
        {"start": "09:00", "end": "09:30", "available_capacity": 2},
        {
            "start": "2026-11-02T09:30:00",
            "end": "2026-11-02T10:00:00",
            "available_capacity": 0,
        },
    ],
}


class FakeBookingApi:
    """Same methods as ``BookingApi``; answers by method name (exceptions are raised)."""

    def __init__(self, **answers):
        self.answers = {
            "filters": FACETS,
            "options": {
                "/api/v1/booking/schemas": SCHEMAS,
                "/api/v1/booking/tags": TAGS,
            },
            "resources": {
                "items": [RESOURCE_CARD],
                "total": 1,
                "page": 1,
                "per_page": 12,
                "pages": 1,
            },
            "resource": RESOURCE,
            "availability": SLOTS,
            "checkout": {"invoice_id": "inv-9", "invoice_number": "BK-1"},
            "bookings": {"bookings": []},
            **answers,
        }
        self.calls = []

    def factory(self, theme_request):
        self.theme_request = theme_request
        return self

    def _answer(self, name, *arguments):
        self.calls.append((name,) + arguments)
        answer = self.answers.get(name)
        if isinstance(answer, Exception):
            raise answer
        if answer is None:
            raise ThemeApiError(404, "Resource not found")
        return answer

    def called(self, name):
        return [call for call in self.calls if call[0] == name]

    def filters(self):
        return self._answer("filters")

    def options(self, endpoint):
        self.calls.append(("options", endpoint))
        answer = self.answers["options"].get(endpoint)
        if isinstance(answer, Exception) or answer is None:
            raise answer or ThemeApiError(404, "Not found")
        return answer

    def resources(self, query):
        return self._answer("resources", dict(query))

    def resource(self, slug):
        return self._answer("resource", slug)

    def availability(self, slug, date):
        return self._answer("availability", slug, date)

    def checkout(self, payload):
        return self._answer("checkout", dict(payload))

    def bookings(self):
        return self._answer("bookings")
