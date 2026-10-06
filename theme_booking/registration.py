"""What theme_booking puts into the theme platform (owner fe-user ``booking``).

fe-user mounts ``/booking``, ``/booking/:slug`` and ``/<bookingFormSlug>/:slug`` as
``CmsPage`` with fixed slugs (``booking``, ``booking-resource-detail``, the form
slug): each themed route renders that CMS page through theme_cms's pipeline with
the route params in context (S152-06 §7). ``/booking/:slug/book/pay`` is the
standalone (noLayout) pay page; its island and confirm fragments are
theme_checkout's own builders over theme_booking's private source registry.
"""
from typing import Any, Callable, Dict, List

from plugins.theme.theme.fragment_registry import ThemeFragment
from plugins.theme.theme.page_registry import PUBLIC_PAGE, ThemePage
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_form import CheckoutForm
from plugins.theme_checkout.theme_checkout.checkout_sources import (
    CheckoutSourceRegistry,
)
from plugins.theme_checkout.theme_checkout.payment_methods import (
    CheckoutPaymentMethodRegistry,
)
from plugins.theme_checkout.theme_checkout.submit import CheckoutSubmit
from plugins.theme_cms.theme_cms.pages import DISPATCH_TEMPLATE
from plugins.theme_cms.theme_cms.registries import ComponentTemplate

from .booking_form import BookingForm
from .catalogue import BookingCatalogue
from .resource_detail import SLOTS_FRAGMENT_PATH, BookingResourceDetail, SlotPicker
from .success import BookingSuccess

BOOKING_FE_USER_PLUGIN = "booking"
BOOKING_PAGE_PRIORITY = 50
FRAGMENT_PREFIX = "/_render/_fragment/booking"
RESOURCES_FRAGMENT_PATH = f"{FRAGMENT_PREFIX}/resources"
PAY_FORM_FRAGMENT_PATH = f"{FRAGMENT_PREFIX}/pay-form"
PAY_SUBMIT_FRAGMENT_PATH = f"{FRAGMENT_PREFIX}/pay-submit"
PAY_PAGE_TEMPLATE = "booking/pay.html.j2"


def _page(rule: str, endpoint: str, template: str, build_context) -> ThemePage:
    return ThemePage(
        rule=rule,
        endpoint=endpoint,
        owner_fe_user_plugin=BOOKING_FE_USER_PLUGIN,
        priority=BOOKING_PAGE_PRIORITY,
        auth=PUBLIC_PAGE,
        template=template,
        build_context=build_context,
    )


def _cms_page_context(
    cms_pages: Any, cms_slug: str
) -> Callable[[ThemeRequest], Dict[str, Any]]:
    def build_context(theme_request: ThemeRequest) -> Dict[str, Any]:
        page_context: Dict[str, Any] = cms_pages.cms_slug_page_context(
            theme_request, cms_slug
        )
        return page_context

    return build_context


def _pay_page_context(theme_request: ThemeRequest) -> Dict[str, Any]:
    """The pay page shell; the island holds everything that needs the pending booking."""
    return {"pay_form_url": PAY_FORM_FRAGMENT_PATH}


def booking_pages(cms_pages: Any, booking_form_slug: str) -> List[ThemePage]:
    cms_routes = (
        ("/booking", "booking_catalogue", "booking"),
        ("/booking/<slug>", "booking_resource", "booking-resource-detail"),
        (f"/{booking_form_slug}/<slug>", "booking_form", booking_form_slug),
    )
    pages = [
        _page(rule, endpoint, DISPATCH_TEMPLATE, _cms_page_context(cms_pages, slug))
        for rule, endpoint, slug in cms_routes
    ]
    pages.append(
        _page(
            "/booking/<slug>/book/pay",
            "booking_checkout",
            PAY_PAGE_TEMPLATE,
            _pay_page_context,
        )
    )
    return pages


def _fragment(
    rule: str, endpoint: str, template: str, build_context, method: str
) -> ThemeFragment:
    return ThemeFragment(
        rule=rule,
        endpoint=endpoint,
        owner_fe_user_plugin=BOOKING_FE_USER_PLUGIN,
        template=template,
        build_context=build_context,
        methods=(method,),
    )


def booking_fragments(
    catalogue: BookingCatalogue,
    source_registry: CheckoutSourceRegistry,
    payment_method_registry: CheckoutPaymentMethodRegistry,
) -> List[ThemeFragment]:
    return [
        _fragment(
            RESOURCES_FRAGMENT_PATH,
            "booking_resources_fragment",
            "booking/_resources_fragment.html.j2",
            catalogue.fragment_context,
            "GET",
        ),
        _fragment(
            SLOTS_FRAGMENT_PATH,
            "booking_slots_fragment",
            "booking/_slots.html.j2",
            SlotPicker().fragment_context,
            "GET",
        ),
        _fragment(
            PAY_FORM_FRAGMENT_PATH,
            "booking_pay_form_fragment",
            "booking/_pay_island.html.j2",
            CheckoutForm(source_registry).context,
            "POST",
        ),
        _fragment(
            PAY_SUBMIT_FRAGMENT_PATH,
            "booking_pay_submit_fragment",
            "checkout/_submit_result.html.j2",
            CheckoutSubmit(source_registry, payment_method_registry).context,
            "POST",
        ),
    ]


def _no_context(widget_config, page, route_params, theme_request) -> Dict[str, Any]:
    """BookingCancel shows fixed copy and links only."""
    return {}


def booking_components(
    catalogue: BookingCatalogue, booking_form_slug: str
) -> List[ComponentTemplate]:
    """The twins of fe-user ``registerCmsVueComponent`` (same names)."""
    return [
        ComponentTemplate(
            "BookingCatalogue",
            "booking/components/booking_catalogue.html.j2",
            catalogue.build_context,
        ),
        ComponentTemplate(
            "BookingResourceDetail",
            "booking/components/booking_resource_detail.html.j2",
            BookingResourceDetail(booking_form_slug).build_context,
        ),
        ComponentTemplate(
            "BookingForm",
            "booking/components/booking_form.html.j2",
            BookingForm().build_context,
        ),
        ComponentTemplate(
            "BookingSuccess",
            "booking/components/booking_success.html.j2",
            BookingSuccess().build_context,
        ),
        ComponentTemplate(
            "BookingCancel", "booking/components/booking_cancel.html.j2", _no_context
        ),
    ]
