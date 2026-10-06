"""S152-09 — theme_booking markup keeps the SPA's DOM contract (D2).

``BookingCatalogue.vue`` (+ fe-core ``CatalogueFilterBar``),
``BookingResourceDetail.vue``, ``BookingForm.vue``, ``BookingCheckout.vue``,
``BookingSuccess.vue`` and ``BookingCancel.vue``: same testids, classes and
English copy, plus the runtime hooks (``data-vbwd-booking-*``) and the shared
checkout blocks on the pay island.
"""
import json
import re

import pytest

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_booking.tests.unit.fakes import FLEXIBLE_RESOURCE, FakeBookingApi
from plugins.theme_booking.tests.unit.template_harness import (
    render,
    render_component,
    theme_plugin,
)
from plugins.theme_booking.tests.unit.test_checkout_source import PENDING_FIELDS
from plugins.theme_booking.tests.unit.test_success import INVOICE
from plugins.theme_booking.theme_booking.booking_form import BookingForm
from plugins.theme_booking.theme_booking.catalogue import BookingCatalogue
from plugins.theme_booking.theme_booking.checkout_source import BookingCheckout
from plugins.theme_booking.theme_booking.resource_detail import (
    BookingResourceDetail,
    SlotPicker,
)
from plugins.theme_booking.theme_booking.success import BookingSuccess
from plugins.theme_checkout.tests.unit.fakes import FakeCheckoutApi, FakeThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_form import CheckoutForm
from plugins.theme_checkout.theme_checkout.checkout_sources import (
    CheckoutSourceRegistry,
)

SIGNED_IN = {"user": {"email": "test@example.com"}, "details": {}}


@pytest.fixture(scope="module")
def plugin():
    return theme_plugin()


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def _testid(html, testid):
    return re.search(rf'<[^>]*data-testid="{re.escape(testid)}"[^>]*>', html)


def _catalogue_html(plugin, query=None, api=None):
    context = BookingCatalogue(
        (api or FakeBookingApi()).factory, FakeCheckoutApi().factory
    ).build_context({}, {}, {}, FakeThemeRequest(query or {}, path="/booking"))
    return render_component(
        plugin, "booking/components/booking_catalogue.html.j2", context
    )


def test_the_catalogue_renders_header_filters_cards_and_pager(plugin):
    api = FakeBookingApi(
        resources={"items": FakeBookingApi().answers["resources"]["items"], "pages": 2}
    )
    html = _catalogue_html(plugin, {"tags": "quiet"}, api)

    assert '<div class="booking-catalogue" data-testid="booking-catalogue">' in html
    assert re.search(r'<h1 class="booking-catalogue__title">\s*Booking\s*</h1>', html)
    search = _testid(html, "booking-catalogue-search").group(0)
    assert 'placeholder="Search resources..."' in search and 'name="q"' in search
    assert 'hx-get="/_render/_fragment/booking/resources"' in search
    toggle = re.search(
        r'<button class="booking-catalogue__view-toggle"[^>]*>', html
    ).group(0)
    assert 'title="Switch to list"' in toggle and 'name="toggle_view"' in toggle
    assert _testid(html, "catalogue-filter-bar")
    assert _testid(html, "catalogue-facet-daterange-availability-from")
    assert '<div class="ghrm-grid">' in html
    card = re.search(
        r'<a href="/booking/dr-smith" class="ghrm-pkg-card" '
        r'data-testid="booking-resource-card-dr-smith">',
        html,
    )
    assert card
    assert re.search(r'data-testid="booking-resource-name">\s*Dr\. Smith\s*<', html)
    assert re.search(
        r'<button type="submit" form="booking-catalogue-form" name="toggle_tag" '
        r'value="quiet" class="booking-card-tag booking-card-tag--active" '
        r'data-testid="booking-resource-tag-dr-smith-quiet">\s*Quiet\s*</button>',
        html,
    )
    assert re.search(
        r'<span class="booking-price"><span class="price-display">'
        r'<span class="price-display__amount" data-testid="price-amount">€50\.00</span>'
        r"</span> / session</span>",
        html,
    )
    assert re.search(r'<span class="ghrm-pkg-downloads">\s*3 spots\s*</span>', html)
    assert _testid(html, "booking-catalogue-pager")
    assert re.search(r'data-testid="booking-catalogue-prev"[^>]*disabled', html)


def test_the_catalogue_list_view_and_its_states(plugin):
    listed = _catalogue_html(plugin, {"view": "list"})
    empty = _catalogue_html(plugin, api=FakeBookingApi(resources={"items": []}))
    failed = _catalogue_html(
        plugin, api=FakeBookingApi(resources=ThemeApiError(500, "boom"))
    )

    assert '<div class="ghrm-list">' in listed and 'class="ghrm-pkg-row"' in listed
    assert 'title="Switch to grid"' in listed
    assert re.search(
        r'<div class="ghrm-empty" data-testid="booking-catalogue-empty">\s*'
        r"No resources available\.\s*</div>",
        empty,
    )
    assert re.search(
        r'<div class="ghrm-empty" data-testid="booking-catalogue-error">\s*boom\s*</div>',
        failed,
    )


def _detail_html(plugin, api=None):
    context = BookingResourceDetail(
        "booking-form", (api or FakeBookingApi()).factory, FakeCheckoutApi().factory
    ).build_context(
        {}, {}, {"slug": "dr-smith"}, FakeThemeRequest(path="/booking/dr-smith")
    )
    return render_component(
        plugin, "booking/components/booking_resource_detail.html.j2", context
    )


def test_the_resource_detail_header_badges_and_gallery(plugin):
    html = _detail_html(plugin)

    assert re.search(r'<h1 class="ghrm-detail-name">\s*Dr\. Smith\s*</h1>', html)
    assert re.search(r'<p class="ghrm-detail-author">\s*specialist\s*</p>', html)
    assert re.search(
        r'<span class="ghrm-badge ghrm-badge--version"><span class="price-display">'
        r'<span class="price-display__amount" data-testid="price-amount">€50\.00</span>',
        html,
    )
    assert re.search(r'ghrm-badge--downloads">\s*Health\s*</span>', html)
    assert 'class="booking-gallery__main-img" data-vbwd-booking-main-image' in html
    assert re.search(
        r'<button type="button" class="booking-gallery__thumb active" '
        r'data-vbwd-booking-thumb="/uploads/smith\.png">',
        html,
    )
    assert 'class="ghrm-detail-icon"' not in html


def test_the_resource_detail_slot_picker_and_book_now(plugin):
    html = _detail_html(plugin)

    form = re.search(r"<form [^>]*data-vbwd-booking-book[^>]*>", html).group(0)
    assert 'method="get"' in form and 'action="/booking-form/dr-smith"' in form
    assert re.search(r'<h3 class="ghrm-section-label">\s*Availability\s*</h3>', html)
    assert re.search(r"<label>\s*Select date:\s*</label>", html)
    date_input = re.search(r'<input type="date" name="date"[^>]*>', html).group(0)
    assert 'hx-get="/_render/_fragment/booking/slots"' in date_input
    assert 'hx-trigger="change"' in date_input
    assert json.loads(re.search(r"hx-vals='([^']*)'", date_input).group(1)) == {
        "resource": "dr-smith"
    }
    assert re.search(
        r'<p class="ghrm-muted">\s*Pick a date to see available slots\.\s*</p>', html
    )
    assert re.search(
        r'<button type="submit" class="ghrm-cta-btn" disabled data-vbwd-booking-book-now>'
        r"\s*Book Now\s*</button>",
        html,
    )
    assert re.search(
        r'<a href="/booking" class="booking-back-link">\s*← Back to catalogue\s*</a>',
        html,
    )


def test_a_flexible_resource_picks_check_in_and_check_out(plugin):
    html = _detail_html(plugin, FakeBookingApi(resource=FLEXIBLE_RESOURCE))

    assert re.search(r"<label>\s*Check-in Date\s*</label>", html)
    assert re.search(r"<label>\s*Check-out Date\s*</label>", html)
    assert re.search(
        r'<input type="date" name="end_date"[^>]*data-vbwd-booking-check-out', html
    )
    assert "hx-get" not in html


def test_the_resource_detail_not_found(plugin):
    html = _detail_html(plugin, FakeBookingApi(resource=ThemeApiError(404, "x")))

    assert re.search(r'<div class="ghrm-error">\s*Resource not found\s*</div>', html)


def test_the_slots_fragment_renders_slots_and_resets_the_picked_slot(plugin):
    context = SlotPicker(FakeBookingApi().factory).fragment_context(
        FakeThemeRequest({"resource": "dr-smith", "date": "2026-11-02"})
    )
    html = render(plugin, "booking/_slots.html.j2", context)

    assert '<input type="hidden" name="start" value="" data-vbwd-booking-start>' in html
    assert '<input type="hidden" name="end" value="" data-vbwd-booking-end>' in html
    assert re.search(
        r'<button type="button" class="booking-slot" data-vbwd-booking-slot '
        r'data-start="09:00" data-end="09:30">\s*'
        r'<span class="booking-slot__time">09:00 – 09:30</span>\s*'
        r'<span class="booking-slot__capacity">2 available</span>',
        html,
    )
    assert re.search(r'class="booking-slot full"[^>]*disabled>', html)


def test_the_slots_fragment_without_slots(plugin):
    html = render(plugin, "booking/_slots.html.j2", {"state": "no_slots", "slots": []})

    assert re.search(
        r'<p class="ghrm-muted">\s*No slots available for this date\.\s*</p>', html
    )


def _form_html(plugin, api=None):
    context = BookingForm(
        (api or FakeBookingApi()).factory, FakeCheckoutApi().factory
    ).build_context(
        {},
        {},
        {"slug": "dr-smith"},
        FakeThemeRequest({"date": "2026-11-02", "start": "09:00", "end": "09:30"}),
    )
    return render_component(plugin, "booking/components/booking_form.html.j2", context)


def test_the_booking_form_summary_fields_and_submit(plugin):
    html = _form_html(plugin)

    assert re.search(r'<h1 class="ghrm-detail-name">\s*Book: Dr\. Smith\s*</h1>', html)
    assert re.search(
        r'<p class="ghrm-detail-author">\s*specialist · 50\.00 EUR / session\s*</p>',
        html,
    )
    assert re.search(
        r'<span class="booking-slot-summary__label">\s*Date &amp; Time\s*</span>\s*'
        r"<span>\s*2026-11-02  09:00 – 09:30\s*</span>",
        html,
    )
    form = re.search(r'<form class="booking-form"[^>]*>', html).group(0)
    assert (
        'action="/booking/dr-smith/book/pay"' in form
        and "data-vbwd-booking-form" in form
    )
    for name, value in (
        ("resource_slug", "dr-smith"),
        ("start_at", "2026-11-02T09:00:00"),
        ("end_at", "2026-11-02T09:30:00"),
    ):
        assert f'<input type="hidden" name="{name}" value="{value}">' in html
    assert re.search(
        r'<h3 class="ghrm-section-label">\s*Additional Information\s*</h3>', html
    )
    assert re.search(
        r'<div class="booking-form__field">\s*<label for="field-symptoms">\s*Symptoms\s*'
        r'<span class="booking-form__required">\*</span>\s*</label>\s*'
        r'<input id="field-symptoms" type="text" name="custom_fields\.symptoms" required '
        r'class="booking-form__input">',
        html,
    )
    assert re.search(
        r'<input id="field-visits" type="number" name="custom_fields\.visits" '
        r'class="booking-form__input">',
        html,
    )
    assert re.search(
        r'<label class="booking-form__checkbox">\s*<input id="field-insured" '
        r'type="checkbox" name="custom_fields\.insured">\s*Insured\s*</label>',
        html,
    )
    assert re.search(
        r'<textarea name="notes" class="booking-form__input" rows="3" '
        r'placeholder="Any special requests\.\.\."></textarea>',
        html,
    )
    assert re.search(
        r'<button type="submit" class="ghrm-cta-btn">\s*Confirm Booking\s*</button>',
        html,
    )
    assert re.search(
        r'<a href="/booking/dr-smith" class="booking-back-link">\s*Cancel\s*</a>', html
    )


def test_the_pay_page_is_a_bare_document_with_the_island(plugin):
    html = render(
        plugin,
        "booking/pay.html.j2",
        {"pay_form_url": "/_render/_fragment/booking/pay-form"},
    )

    assert '<meta name="vbwd-frontend" content="theme">' in html
    assert re.search(
        r'<div class="public-checkout">\s*<h1 data-testid="checkout-title">\s*'
        r"Booking Confirmation &amp; Payment\s*</h1>",
        html,
    )
    island = re.search(r'<div class="booking-pay-island"[^>]*>', html).group(0)
    assert 'id="booking-pay-island"' in island and "data-vbwd-booking-pending" in island
    assert 'hx-post="/_render/_fragment/booking/pay-form"' in island
    assert (
        'hx-trigger="load, vbwd:session-started from:body, vbwd:session-ended from:body"'
        in island
    )
    assert json.loads(re.search(r"hx-vals='([^']*)'", island).group(1)) == {
        "source": "booking"
    }
    assert "window.VbwdCheckout" in html and "window.VbwdBooking" in html
    assert 'class="cms-layout' not in html


def _island_html(plugin, checkout_api=None, coupon_code=None):
    checkout_api = checkout_api or FakeCheckoutApi(profile=SIGNED_IN)
    registry = CheckoutSourceRegistry()
    registry.register(
        BookingCheckout(
            FakeBookingApi().factory, checkout_api.factory
        ).checkout_source()
    )
    form = {"pending": json.dumps(PENDING_FIELDS), "source": "booking"}
    if coupon_code:
        form.update({"coupon_input": coupon_code, "coupon_action": "apply"})
    context = CheckoutForm(registry, checkout_api.factory).context(
        FakeThemeRequest(form)
    )
    return render(plugin, "booking/_pay_island.html.j2", context)


def test_the_pay_island_summary_and_shared_blocks(plugin):
    html = _island_html(plugin)

    form = re.search(r"<form class=\"checkout-content\"[^>]*>", html).group(0)
    assert "data-vbwd-checkout-form" in form and 'data-authenticated="1"' in form
    assert '<input type="hidden" name="source" value="booking">' in html
    assert _testid(html, "email-block-success")
    assert re.search(
        r'<div class="card order-summary">\s*<h2>\s*Order Summary\s*</h2>', html
    )
    assert re.search(
        r'<a href="/booking/dr-smith" class="booking-resource-name">\s*Dr\. Smith\s*</a>',
        html,
    )
    assert re.search(
        r'<span class="booking-resource-price" data-testid="resource-price">', html
    )
    assert re.search(
        r'<div class="booking-detail-row">\s*<span>\s*Date &amp; Time\s*</span>\s*'
        r"<span>\s*11/2/2026, 9:00:00 AM — 11/2/2026, 9:30:00 AM\s*</span>",
        html,
    )
    assert re.search(r"<span>\s*symptoms\s*</span>\s*<span>\s*Headache\s*</span>", html)
    assert re.search(
        r"<span>\s*Notes\s*</span>\s*<span>\s*E2E test booking\s*</span>", html
    )
    assert re.search(
        r'<div class="total" data-testid="order-total">\s*'
        r'<strong data-testid="order-total-amount">\s*Total: €50\.00\s*</strong>',
        html,
    )
    assert _testid(html, "billing-address-block")
    assert _testid(html, "payment-methods-block")
    assert re.search(
        r'<label for="method-stripe" class="method-name">Pay with Stripe</label>', html
    )
    assert re.search(
        r'<label for="method-invoice" class="method-name">Invoice</label>', html
    )
    assert _testid(html, "terms-checkbox")
    pay = re.search(
        r'<button type="button" class="btn primary pay-button"[^>]*>', html
    ).group(0)
    assert 'hx-post="/_render/_fragment/booking/pay-submit"' in pay
    assert 'data-testid="confirm-checkout"' in pay and "disabled" in pay
    assert re.search(
        r'class="btn primary pay-button"[^>]*>\s*Pay Now €50\.00\s*</button>', html
    )
    assert re.search(
        r'<a href="/booking/dr-smith" class="btn secondary">\s*Cancel\s*</a>', html
    )


def test_the_pay_island_lists_the_spa_requirements(plugin):
    html = _island_html(plugin, FakeCheckoutApi())

    assert re.search(r"<p><strong>\s*Before you can pay:\s*</strong></p>", html)
    for requirement, copy in (
        ("signIn", "Please log in or create an account"),
        ("paymentMethod", "Select a payment method"),
        ("billingAddress", "Enter billing address"),
        ("acceptTerms", "Accept the terms and conditions"),
    ):
        assert re.search(
            rf'<li data-requirement="{requirement}"[^>]*>\s*{copy}\s*</li>', html
        )
    assert 'type="email"' in html


def test_the_pay_island_coupon_posts_back_to_the_booking_island(plugin):
    checkout_api = FakeCheckoutApi(
        profile=SIGNED_IN, validate_coupon={"valid": True, "discount_amount": "10.00"}
    )
    html = _island_html(plugin, checkout_api, coupon_code="SAVE10")

    assert re.search(
        r'data-testid="coupon-clear"[^>]*hx-post="/_render/_fragment/booking/pay-form"'
        r'[^>]*hx-target="#booking-pay-island"',
        html,
    )
    assert re.search(r"Final price with coupon: €40\.00", html)
    assert re.search(
        r'data-testid="order-discount">\s*You have saved: €10\.00\s*<', html
    )


def test_a_free_booking_confirms_without_payment_methods(plugin):
    free = {**FakeBookingApi().answers["resource"], "pricing": None, "price": "0.00"}
    checkout_api = FakeCheckoutApi(profile=SIGNED_IN)
    registry = CheckoutSourceRegistry()
    registry.register(
        BookingCheckout(
            FakeBookingApi(resource=free).factory, checkout_api.factory
        ).checkout_source()
    )
    context = CheckoutForm(registry, checkout_api.factory).context(
        FakeThemeRequest({"pending": json.dumps(PENDING_FIELDS), "source": "booking"})
    )
    html = render(plugin, "booking/_pay_island.html.j2", context)

    assert not _testid(html, "payment-methods-block")
    assert not _testid(html, "billing-address-block")
    assert re.search(r"pay-button[^>]*>\s*Confirm Free Booking\s*</button>", html)


def test_the_pay_island_without_a_pending_booking(plugin):
    registry = CheckoutSourceRegistry()
    registry.register(BookingCheckout(FakeBookingApi().factory).checkout_source())
    context = CheckoutForm(registry, FakeCheckoutApi().factory).context(
        FakeThemeRequest({"source": "booking"})
    )
    html = render(plugin, "booking/_pay_island.html.j2", context)

    assert re.search(
        r'<div class="error-state">\s*<p>\s*Booking not found\.\s*</p>', html
    )
    assert re.search(
        r'<a href="/booking" class="btn secondary">\s*Back to catalogue\s*</a>', html
    )


def _success_html(plugin, user_id="user-a"):
    context = BookingSuccess(
        FakeBookingApi().factory, FakeCheckoutApi(invoice={"invoice": INVOICE}).factory
    ).build_context(
        {}, {}, {}, FakeThemeRequest({"invoice_id": "inv-9"}, user_id=user_id)
    )
    return render_component(
        plugin, "booking/components/booking_success.html.j2", context
    )


def test_the_success_page_banner_invoice_and_booking_cards(plugin):
    html = _success_html(plugin)

    assert re.search(
        r'<div class="confirmation-banner confirmation-banner--paid">\s*'
        r"<h1>\s*Booking Confirmed!\s*</h1>",
        html,
    )
    assert re.search(
        r'<span class="confirmation-value confirmation-mono">\s*BK-1A2B3C4D\s*</span>',
        html,
    )
    assert re.search(r'<span class="status-badge paid">\s*paid\s*</span>', html)
    assert re.search(
        r'<div class="price-breakdown" data-testid="booking-breakdown">', html
    )
    assert re.search(
        r"<span class=\"price-breakdown__label\">\s*TAX 0%\s*</span>", html
    )
    assert re.search(r"<h2>\s*Booking Details\s*</h2>", html)
    assert re.search(r'<p class="resource-type">\s*specialist\s*</p>', html)
    assert re.search(
        r'<span class="confirmation-label">\s*Date &amp; Time\s*</span>', html
    )
    assert re.search(
        r'<a href="/booking" class="btn secondary">\s*Back to catalogue\s*</a>', html
    )
    assert re.search(
        r'<a href="/dashboard/bookings" class="btn primary">\s*View My Bookings\s*</a>',
        html,
    )


def test_the_anonymous_success_page_is_the_pending_banner(plugin):
    html = _success_html(plugin, user_id=None)

    assert re.search(r"<h1>\s*Payment Processing\s*</h1>", html)
    assert 'class="card"' not in html


def test_the_cancel_page(plugin):
    html = render_component(plugin, "booking/components/booking_cancel.html.j2", {})

    assert re.search(
        r'<div class="booking-cancel">\s*<div class="cancel-banner">\s*'
        r"<h1>\s*Payment Cancelled\s*</h1>",
        html,
    )
    assert re.search(
        r'<a href="/booking" class="btn primary">\s*Browse Resources\s*</a>', html
    )
    assert re.search(
        r'<a href="#" class="btn secondary" data-vbwd-history-back>\s*Try Again\s*</a>',
        html,
    )
