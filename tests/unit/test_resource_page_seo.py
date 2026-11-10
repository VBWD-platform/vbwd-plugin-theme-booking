"""S154 D7 — the themed ``/booking/<slug>`` page owns its SEO head.

fe-user mounts ``/booking/:slug`` inside the template CMS page
``booking-resource-detail`` (seeded ``noindex``), so left alone every resource
carried the template's robots, title and canonical. The route reads the resource
(``GET /api/v1/booking/resources/<slug>``) and hands theme_cms ``SeoOverrides``:
the resource name, a self canonical, and robots from booking's
``seo_index_resources`` switch (``seo_indexable`` on the payload):
``index,follow`` on, ``noindex,follow`` off. A missing resource — the public
endpoint also 404s an inactive one — is the ``ThemeApiError`` 404, i.e. the
labelled themed 404.
"""
from types import MappingProxyType, SimpleNamespace

import pytest

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_booking.tests.unit.fakes import RESOURCE, FakeBookingApi
from plugins.theme_booking.theme_booking.resource_page_seo import (
    BookingResourcePageSeo,
)
from plugins.theme_cms.theme_cms.page_context import SeoOverrides


class _RecordingCmsPages:
    def __init__(self):
        self.rendered = []

    def cms_slug_page_context(self, theme_request, cms_slug, seo_overrides=None):
        self.rendered.append((cms_slug, seo_overrides))
        return {"page_title": "rendered"}


def _request(slug):
    return SimpleNamespace(view_args=MappingProxyType({"slug": slug}))


def _page_seo(**answers):
    cms_pages = _RecordingCmsPages()
    api = FakeBookingApi(**answers)
    return BookingResourcePageSeo(cms_pages, api.factory), cms_pages, api


def test_a_resource_renders_its_template_page_with_its_own_seo_head():
    page_seo, cms_pages, api = _page_seo(resource={**RESOURCE, "seo_indexable": True})

    context = page_seo.context(_request(RESOURCE["slug"]))

    assert context == {"page_title": "rendered"}
    assert api.called("resource") == [("resource", RESOURCE["slug"])]
    assert cms_pages.rendered == [
        (
            "booking-resource-detail",
            SeoOverrides(
                title=RESOURCE["name"],
                robots="index,follow",
                canonical_path=f"/booking/{RESOURCE['slug']}",
            ),
        )
    ]


def test_a_switched_off_resource_is_noindex_follow():
    page_seo, cms_pages, _ = _page_seo(resource={**RESOURCE, "seo_indexable": False})

    page_seo.context(_request(RESOURCE["slug"]))

    assert cms_pages.rendered[0][1].robots == "noindex,follow"


def test_a_missing_or_inactive_resource_is_a_404():
    page_seo, cms_pages, _ = _page_seo(resource=None)

    with pytest.raises(ThemeApiError) as raised:
        page_seo.context(_request("no-such-resource"))

    assert raised.value.status == 404
    assert cms_pages.rendered == []


def test_the_canonical_path_escapes_the_slug_segment():
    odd_slug = {**RESOURCE, "slug": "room 1/2"}
    page_seo, cms_pages, _ = _page_seo(resource=odd_slug)

    page_seo.context(_request("room 1/2"))

    assert cms_pages.rendered[0][1].canonical_path == "/booking/room%201%2F2"
