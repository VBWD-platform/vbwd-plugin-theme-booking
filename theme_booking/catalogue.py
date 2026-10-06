"""The BookingCatalogue CMS component — the twin of ``BookingCatalogue.vue`` (S152-09).

Facets come from ``GET /api/v1/booking/filters`` (shared loader); resources from
``GET /api/v1/booking/resources`` with the SPA's query (``useCatalogueFilters``:
the reserved ``page`` / ``q`` / ``tags``, every other query value a facet). The
toolbar and the fe-core filter bar are one GET form, so the page works without
JavaScript, and htmx swaps the whole catalogue from
``/_render/_fragment/booking/resources``. A chip submits ``toggle_tag``, the
grid/list switch ``toggle_view`` (the SPA keeps that choice in the component;
here it rides in the form), a pager button its ``page``; any other change starts
again at page 1. Card prices are in the app default currency (``GET
/api/v1/config`` through theme_checkout's ``CheckoutApi``, once per render).
"""
from typing import Any, Callable, Dict, List, Mapping, Optional

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_api import CheckoutApi
from plugins.theme_checkout.theme_checkout.price_display import price_display_view
from plugins.theme_cms.theme_cms.components.catalogue_filters import load_facets

from .booking_api import BookingApi

DEFAULT_PER_PAGE = 12
FIRST_PAGE = 1
TAGS_FACET = "tags"
TAG_SEPARATOR = ","
GRID_VIEW = "grid"
LIST_VIEW = "list"
LOAD_FAILED_MESSAGE = "Failed to load resources"
CATALOG_PATH_FIELD = "catalog_path"
DEFAULT_CATALOG_PATH = "/booking"
PRICE_UNIT_PREFIX = "per_"
# Fields the themed form carries for itself — never facets sent to the API.
FORM_ONLY_FIELDS = ("page", "q", TAGS_FACET, "toggle_tag", "view", "toggle_view")
THEME_ONLY_FIELDS = FORM_ONLY_FIELDS + (CATALOG_PATH_FIELD,)

ApiFactory = Callable[[ThemeRequest], Any]


def _page_number(raw_page: Any) -> int:
    try:
        return max(int(raw_page), FIRST_PAGE)
    except (TypeError, ValueError):
        return FIRST_PAGE


def _toggled(tags: List[str], tag: str) -> List[str]:
    return (
        [current for current in tags if current != tag] if tag in tags else tags + [tag]
    )


def _view_mode(query_args: Mapping[str, Any]) -> str:
    current = LIST_VIEW if query_args.get("view") == LIST_VIEW else GRID_VIEW
    if not query_args.get("toggle_view"):
        return current
    return GRID_VIEW if current == LIST_VIEW else LIST_VIEW


def catalogue_filters(query_args: Mapping[str, Any]) -> Dict[str, Any]:
    """The catalogue state the form / URL carries; facet values keyed by name."""
    tags = [
        tag for tag in (query_args.get(TAGS_FACET) or "").split(TAG_SEPARATOR) if tag
    ]
    toggle_tag = query_args.get("toggle_tag")
    if toggle_tag:
        tags = _toggled(tags, toggle_tag)
    facet_values = {
        key: value
        for key, value in query_args.items()
        if key not in THEME_ONLY_FIELDS and value
    }
    return {
        **facet_values,
        "q": (query_args.get("q") or "").strip(),
        "tags": tags,
        "page": FIRST_PAGE if toggle_tag else _page_number(query_args.get("page")),
    }


def _resources_query(filters: Mapping[str, Any]) -> Dict[str, Any]:
    """``buildResourcesUrl`` — empty values are left out."""
    query: Dict[str, Any] = {"page": filters["page"], "per_page": DEFAULT_PER_PAGE}
    if filters["q"]:
        query["q"] = filters["q"]
    if filters["tags"]:
        query[TAGS_FACET] = TAG_SEPARATOR.join(filters["tags"])
    for key, value in filters.items():
        if key not in FORM_ONLY_FIELDS:
            query[key] = value
    return query


def _nullish(value: Any, fallback: Any) -> Any:
    """JavaScript's ``value ?? fallback``."""
    return fallback if value is None else value


def resource_price(resource: Mapping[str, Any], currency: str) -> Any:
    """The resource's PriceDisplay (``pricing.net ?? price`` / ``gross ?? price``)
    in the app default ``currency`` (``:currency="appConfig.defaultCurrency"``)."""
    pricing = resource.get("pricing") or {}
    price = resource.get("price")
    return price_display_view(
        _nullish(pricing.get("net_amount"), price),
        _nullish(pricing.get("gross_amount"), price),
        currency,
        pricing.get("effective_display_mode"),
        pricing.get("prices_display_mode"),
    )


def price_unit(resource: Mapping[str, Any]) -> str:
    """``price_unit.replace('per_', '')``."""
    return str(resource.get("price_unit") or "").replace(PRICE_UNIT_PREFIX, "", 1)


def _card(
    resource: Mapping[str, Any],
    tag_labels: Mapping[str, str],
    active_tags: List[str],
    currency: str,
) -> Dict[str, Any]:
    return {
        "slug": resource.get("slug") or "",
        "name": resource.get("name") or "",
        "href": f"/booking/{resource.get('slug')}",
        "image_url": resource.get("image_url"),
        "resource_type": resource.get("resource_type") or "",
        "description": resource.get("description"),
        "price": resource_price(resource, currency),
        "price_unit": price_unit(resource),
        "capacity": int(resource.get("capacity") or 0),
        "tags": [
            {
                "slug": tag,
                "label": tag_labels.get(tag, tag),
                "active": tag in active_tags,
            }
            for tag in resource.get("tags") or []
        ],
    }


def _pager(current_page: int, total_pages: int) -> Optional[Dict[str, Any]]:
    if total_pages <= FIRST_PAGE:
        return None
    return {
        "current": current_page,
        "total": total_pages,
        "previous": current_page - 1 if current_page > FIRST_PAGE else None,
        "next": current_page + 1 if current_page < total_pages else None,
    }


class BookingCatalogue:
    """``build_context`` (the component) and the catalogue fragment's context."""

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
        return self._catalogue(theme_request, theme_request.path)

    def fragment_context(self, theme_request: ThemeRequest) -> Dict[str, Any]:
        catalog_path = (
            theme_request.query_args.get(CATALOG_PATH_FIELD) or DEFAULT_CATALOG_PATH
        )
        return {"component_context": self._catalogue(theme_request, catalog_path)}

    def _catalogue(
        self, theme_request: ThemeRequest, form_action: str
    ) -> Dict[str, Any]:
        api = self._api_factory(theme_request)
        filters = catalogue_filters(theme_request.query_args)
        facets = load_facets(api)
        context: Dict[str, Any] = {
            "form_action": form_action,
            "filters": filters,
            "facets": facets,
            "view_mode": _view_mode(theme_request.query_args),
        }
        try:
            listing = api.resources(_resources_query(filters))
        except ThemeApiError as load_error:
            return {
                **context,
                "state": "error",
                "error": load_error.message or LOAD_FAILED_MESSAGE,
                "pager": None,
            }
        tag_facet = next(
            (facet for facet in facets if facet.get("key") == TAGS_FACET), {}
        )
        tag_labels = {
            option["value"]: option["label"]
            for option in tag_facet.get("options") or []
        }
        currency = self._checkout_api_factory(theme_request).default_currency()
        cards = [
            _card(resource, tag_labels, filters["tags"], currency)
            for resource in listing.get("items") or []
        ]
        return {
            **context,
            "state": "resources" if cards else "empty",
            "resources": cards,
            "pager": _pager(filters["page"], int(listing.get("pages") or FIRST_PAGE)),
        }
