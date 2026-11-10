"""The themed ``/booking/<slug>`` page's own SEO head (S154 D7).

fe-user renders ``/booking/:slug`` inside the fixed CMS page
``booking-resource-detail`` (seeded ``noindex``); left alone, every resource
would carry that template page's robots, title and canonical. The route reads
its resource (``GET /api/v1/booking/resources/<slug>``) and hands theme_cms
``SeoOverrides``: the resource name, a self canonical, and robots from booking's
``seo_index_resources`` switch (``seo_indexable`` on the payload). A missing
resource — the public endpoint also 404s an inactive one — raises the
``ThemeApiError`` 404: the labelled themed 404.
"""
from typing import Any, Callable, Dict

from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_cms.theme_cms.page_context import SeoOverrides
from plugins.theme_cms.theme_cms.seo_indexing import indexable_switch_robots

from .booking_api import BookingApi, path_segment

RESOURCE_PAGE_SLUG = "booking-resource-detail"
RESOURCE_PATH_PREFIX = "/booking/"

ApiFactory = Callable[[ThemeRequest], Any]


class BookingResourcePageSeo:
    """``build_context`` of the resource page."""

    def __init__(self, cms_pages: Any, api_factory: ApiFactory = BookingApi) -> None:
        self._cms_pages = cms_pages
        self._api_factory = api_factory

    def context(self, theme_request: ThemeRequest) -> Dict[str, Any]:
        route_slug = theme_request.view_args.get("slug") or ""
        resource = self._api_factory(theme_request).resource(route_slug)
        overrides = SeoOverrides(
            title=resource.get("name") or None,
            robots=indexable_switch_robots(resource),
            canonical_path=RESOURCE_PATH_PREFIX
            + path_segment(str(resource.get("slug") or route_slug)),
        )
        page_context: Dict[str, Any] = self._cms_pages.cms_slug_page_context(
            theme_request, RESOURCE_PAGE_SLUG, overrides
        )
        return page_context
