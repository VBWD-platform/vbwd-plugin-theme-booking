"""S152-09 — what theme_booking registers on enable.

fe-user mounts ``/booking``, ``/booking/:slug`` and ``/<bookingFormSlug>/:slug``
as ``CmsPage`` with fixed slugs (``booking``, ``booking-resource-detail``, the form
slug): each themed route renders that CMS page with the route params in context.
``/booking/:slug/book/pay`` is the standalone (noLayout) pay page. The catalogue,
slot, pay-island and pay-submit fragments; the five widget twins into theme_cms.
Everything is owned by fe-user ``booking``.
"""
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest
from flask import Flask

from plugins.theme import ThemePlugin
from plugins.theme.theme.page_registry import PUBLIC_PAGE
from plugins.theme_booking import ThemeBookingPlugin
from plugins.theme_booking.theme_booking.plugin_paths import (
    STYLESHEETS_DIRECTORY,
    TEMPLATES_DIRECTORY,
    TRANSLATIONS_DIRECTORY,
)
from plugins.theme_booking.theme_booking.registration import booking_pages
from plugins.theme_checkout import ThemeCheckoutPlugin
from plugins.theme_cms import ThemeCmsPlugin
from plugins.theme_cms.theme_cms.pages import DISPATCH_TEMPLATE

FE_USER_BOOKING = (
    Path(__file__).resolve().parents[5] / "vbwd-fe-user" / "plugins" / "booking"
)
CMS_ROUTES = {
    "/booking": "booking",
    "/booking/<slug>": "booking-resource-detail",
    "/booking-form/<slug>": "booking-form",
}
WIDGETS = (
    "BookingCatalogue",
    "BookingResourceDetail",
    "BookingForm",
    "BookingSuccess",
    "BookingCancel",
)


def _app(plugins, booking_config=None):
    app = Flask(__name__)
    app.plugin_manager = SimpleNamespace(get_plugin=plugins.get)
    app.config_store = SimpleNamespace(
        get_config=lambda name: (booking_config or {})
        if name == "theme_booking"
        else {}
    )
    return app


def _enable(booking_config=None):
    plugins = {
        "theme": ThemePlugin(),
        "theme_cms": ThemeCmsPlugin(),
        "theme_checkout": ThemeCheckoutPlugin(),
        "theme_booking": ThemeBookingPlugin(),
    }
    with _app(plugins, booking_config).app_context():
        for plugin in plugins.values():
            plugin.on_enable()
    return SimpleNamespace(**plugins)


@pytest.fixture
def enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))
    return _enable()


def _pages(enabled):
    return {page.rule: page for page in enabled.theme.page_registry.pages()}


def test_registers_the_four_booking_routes(enabled):
    pages = _pages(enabled)

    for rule in CMS_ROUTES:
        assert pages[rule].owner_fe_user_plugin == "booking", rule
        assert pages[rule].template == DISPATCH_TEMPLATE
        assert pages[rule].auth == PUBLIC_PAGE
    pay = pages["/booking/<slug>/book/pay"]
    assert pay.template == "booking/pay.html.j2"
    assert pay.owner_fe_user_plugin == "booking"
    assert pay.auth == PUBLIC_PAGE


def test_the_form_route_follows_the_configured_form_slug(monkeypatch, tmp_path):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))

    enabled = _enable({"booking_form_slug": "reserve"})

    assert "/reserve/<slug>" in _pages(enabled)
    assert "/booking-form/<slug>" not in _pages(enabled)


def test_each_cms_route_renders_its_cms_page_with_the_route_params():
    rendered = []
    fake_cms_pages = SimpleNamespace(
        cms_slug_page_context=lambda request, slug: rendered.append(
            (slug, dict(request.view_args))
        )
        or {}
    )
    pages = {page.rule: page for page in booking_pages(fake_cms_pages, "booking-form")}

    for rule in CMS_ROUTES:
        pages[rule].build_context(
            SimpleNamespace(view_args=MappingProxyType({"slug": "x"}))
        )

    assert rendered == [(slug, {"slug": "x"}) for slug in CMS_ROUTES.values()]


def test_registers_the_booking_fragments(enabled):
    fragments = {
        fragment.rule: fragment
        for fragment in enabled.theme.fragment_registry.fragments()
        if "/booking/" in fragment.rule
    }

    assert {rule: fragment.methods for rule, fragment in fragments.items()} == {
        "/_render/_fragment/booking/resources": ("GET",),
        "/_render/_fragment/booking/slots": ("GET",),
        "/_render/_fragment/booking/pay-form": ("POST",),
        "/_render/_fragment/booking/pay-submit": ("POST",),
    }
    assert {fragment.owner_fe_user_plugin for fragment in fragments.values()} == {
        "booking"
    }


def test_registers_the_five_widget_twins(enabled):
    for name in WIDGETS:
        assert enabled.theme_cms.component_registry.resolve(name) is not None, name


def test_registers_booking_confirmation_details_as_a_confirmation_section(enabled):
    """``checkoutConfirmationRegistry.register('booking', BookingConfirmationDetails)``."""
    registry = enabled.theme_checkout.confirmation_section_registry
    registry._is_fe_user_plugin_enabled = lambda name: name == "booking"
    booking_invoice = {"line_items": [{"metadata": {"plugin": "booking"}}]}

    sections = registry.sections_for(booking_invoice)

    assert [section.name for section in sections] == ["booking"]
    assert sections[0].owner_fe_user_plugin == "booking"
    assert sections[0].template == "booking/confirmation_details.html.j2"
    assert registry.sections_for({"line_items": []}) == []


def test_booking_is_not_a_source_of_the_generic_checkout(enabled):
    """The SPA's booking pays on its own page, never through ``/checkout``."""
    assert enabled.theme_checkout.source_registry.get("booking") is None


def test_contributes_templates_translations_and_stylesheets(enabled):
    registry = enabled.theme.theme_registry

    assert TEMPLATES_DIRECTORY in registry.contributed_template_paths()
    assert TRANSLATIONS_DIRECTORY in registry.contributed_translation_paths()
    assert STYLESHEETS_DIRECTORY in registry.contributed_stylesheet_paths()


def test_enabling_twice_registers_once(enabled):
    with _app(vars(enabled)).app_context():
        enabled.theme_booking.on_enable()

    assert list(_pages(enabled)).count("/booking") == 1


def test_the_routes_and_widgets_are_the_ones_fe_user_registers():
    index = FE_USER_BOOKING / "index.ts"
    if not index.is_file():
        pytest.skip("fe-user booking plugin is not next to vbwd-backend (plugin CI)")
    source = index.read_text(encoding="utf-8")
    fe_user_config = (FE_USER_BOOKING / "config.json").read_text(encoding="utf-8")

    for path in ("/booking", "/booking/:slug", "/booking/:slug/book/pay"):
        assert f"path: '{path}'" in source
    assert "path: `/${formSlug}/:slug`" in source
    assert '"booking_form_slug": "booking-form"' in fe_user_config
    for slug in ("booking", "booking-resource-detail"):
        assert f"props: {{ slug: '{slug}' }}" in source
    for name in WIDGETS:
        assert f"registerCmsVueComponent('{name}'" in source
