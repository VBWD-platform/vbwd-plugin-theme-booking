"""Theme adapter mirroring the fe-user booking plugin (S152-09).

Renders only when ``VBWD_FRONTEND_MODE=theme``; in the default ``vue`` mode the
Vue SPA serves every page. On enable it contributes its templates, translations
and ported stylesheet and registers the booking routes (the three CMS-layout
pages through theme_cms's pipeline, the standalone pay page), the catalogue,
slot and pay fragments, and the five Booking* widget twins (into theme_cms).
The pay page runs theme_checkout's island over theme_booking's own checkout
source; BookingConfirmationDetails joins theme_checkout's
``/checkout/confirmation`` as a confirmation section. It talks to the backend over the public API only (D3).
"""
from typing import Optional

from flask import current_app

from vbwd.plugins.base import BasePlugin, PluginMetadata

from plugins.theme.theme.page_registry import resolve_theme_plugin
from plugins.theme_booking.theme_booking.catalogue import BookingCatalogue
from plugins.theme_booking.theme_booking.checkout_source import BookingCheckout
from plugins.theme_booking.theme_booking.confirmation_details import (
    BookingConfirmationDetails,
)
from plugins.theme_booking.theme_booking.plugin_paths import (
    STYLESHEETS_DIRECTORY,
    TEMPLATES_DIRECTORY,
    TRANSLATIONS_DIRECTORY,
)
from plugins.theme_booking.theme_booking.registration import (
    booking_components,
    booking_fragments,
    booking_pages,
)
from plugins.theme_checkout.theme_checkout.checkout_sources import (
    THEME_CHECKOUT_PLUGIN_NAME,
    CheckoutSourceRegistry,
)
from plugins.theme_checkout.theme_checkout.confirmation_sections import (
    resolve_confirmation_section_registry,
)
from plugins.theme_cms.theme_cms.pages import CmsPages
from plugins.theme_cms.theme_cms.registries import THEME_CMS_PLUGIN_NAME

BOOKING_FORM_SLUG_CONFIG_KEY = "booking_form_slug"
# fe-user plugins/booking/config.json ``booking.booking_form_slug``.
DEFAULT_BOOKING_FORM_SLUG = "booking-form"


class ThemeBookingPlugin(BasePlugin):
    """Theme adapter mirroring the fe-user booking plugin."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="theme_booking",
            version="1.0.0",
            author="VBWD Team",
            description="Theme adapter mirroring the fe-user booking plugin.",
            dependencies=["theme>=1.0", "booking", "theme_checkout", "theme_cms"],
        )

    def booking_form_slug(self) -> str:
        config_store = getattr(current_app, "config_store", None)
        saved_config = (
            config_store.get_config(self.metadata.name) if config_store else {}
        )
        return (
            saved_config.get(BOOKING_FORM_SLUG_CONFIG_KEY) or DEFAULT_BOOKING_FORM_SLUG
        )

    def on_enable(self) -> None:
        plugin_manager = getattr(current_app, "plugin_manager")
        # Declared dependencies: enabled before this plugin (dependency order).
        theme_cms_plugin = plugin_manager.get_plugin(THEME_CMS_PLUGIN_NAME)
        theme_checkout_plugin = plugin_manager.get_plugin(THEME_CHECKOUT_PLUGIN_NAME)
        theme_plugin = resolve_theme_plugin()
        theme_registry = theme_plugin.theme_registry
        if TEMPLATES_DIRECTORY in theme_registry.contributed_template_paths():
            return
        booking_form_slug = self.booking_form_slug()
        catalogue = BookingCatalogue()
        for component in booking_components(catalogue, booking_form_slug):
            if theme_cms_plugin.component_registry.resolve(component.name) is None:
                theme_cms_plugin.component_registry.register(component)
        theme_registry.add_contributed_template_path(TEMPLATES_DIRECTORY)
        theme_registry.add_contributed_translation_path(TRANSLATIONS_DIRECTORY)
        theme_registry.add_contributed_stylesheet_path(STYLESHEETS_DIRECTORY)
        cms_pages = CmsPages(
            theme_cms_plugin.page_type_registry, theme_cms_plugin.component_registry
        )
        for page in booking_pages(cms_pages, booking_form_slug):
            theme_plugin.page_registry.register(page)
        # Private: the SPA's booking pays on its own page, never through /checkout.
        source_registry = CheckoutSourceRegistry()
        source_registry.register(BookingCheckout().checkout_source())
        for fragment in booking_fragments(
            catalogue, source_registry, theme_checkout_plugin.payment_method_registry
        ):
            theme_plugin.fragment_registry.register(fragment)
        resolve_confirmation_section_registry().register(
            BookingConfirmationDetails().section()
        )

    def get_url_prefix(self) -> Optional[str]:
        # No blueprint of its own: the theme mounts the registered pages.
        return ""
