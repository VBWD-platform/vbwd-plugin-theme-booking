"""S152-09 — the SPA's structural CSS for the booking views.

S152-06c rules (theme ``tests/css_inventory`` helpers): every class a theme_booking
template or runtime uses that the mirrored Vue component styles has a ported
rule, no invented rule. S152-06d colour tokens (theme ``tests/colour_tokens``): a
literal colour appears only as the fallback of a ``var(--vbwd-…, <literal>)``
token; every SPA colour of a used rule is ported with its exact literal (minus
the justified :data:`EXCLUDED_DECLARATIONS`); every ``--vbwd-booking-*`` token is
documented in the theme guide. The SPA-comparing half skips without fe-user.

The checkout-wide rules the pay page shares (``.card``, ``.btn``, ``.public-checkout``,
the states, the spinner) are theme_checkout's (S152-07c); theme_booking declares
it as a dependency, so its stylesheet loads first. Class and colour coverage
therefore count theme_checkout's CSS as available; booking's own CSS keeps only
booking rules.
"""
import re
from pathlib import Path

import pytest

from plugins.theme.theme.theme_registry import TOKEN_NAME_PATTERN
from plugins.theme_booking.theme_booking.plugin_paths import (
    STYLESHEETS_DIRECTORY,
    TEMPLATES_DIRECTORY,
)
from plugins.theme_checkout.theme_checkout.plugin_paths import (
    STYLESHEETS_DIRECTORY as CHECKOUT_STYLESHEETS_DIRECTORY,
)
from plugins.theme.tests.colour_tokens import (
    adapter_token_fallbacks,
    css_declarations,
    documented_colour_tokens,
    token_fallback_mismatches,
    unported_spa_colours,
)
from plugins.theme.tests.css_inventory import (
    hard_coded_colours,
    is_used,
    rule_classes,
    script_classes,
    template_class_usage,
    vue_style_text,
)

BACKEND_ROOT = Path(__file__).resolve().parents[4]
FE_USER_ROOT = BACKEND_ROOT.parent / "vbwd-fe-user"
BOOKING_VIEWS = FE_USER_ROOT / "plugins" / "booking" / "booking" / "views"
SOURCE_STYLE_FILES = (
    BOOKING_VIEWS / "BookingCatalogue.vue",
    BOOKING_VIEWS / "BookingResourceDetail.vue",
    BOOKING_VIEWS / "BookingForm.vue",
    BOOKING_VIEWS / "BookingCheckout.vue",
    BOOKING_VIEWS / "BookingSuccess.vue",
    BOOKING_VIEWS / "BookingCancel.vue",
    BOOKING_VIEWS.parent / "components" / "BookingConfirmationDetails.vue",
    FE_USER_ROOT / "vue" / "src" / "components" / "PriceBreakdown.vue",
)
# SPA colour declarations deliberately NOT ported (each with its reason).
SHARED_CLASS_KEPT = (
    "the SPA scopes each view; the port keeps BookingResourceDetail.vue's value "
    "for the class both views share"
)
DEAD_IN_THE_SPA = (
    "dead in the SPA: the next `.ghrm-error { color: #dc2626 }` rule overrides it "
    "(the shared `.ghrm-loading, .ghrm-error` rule; .ghrm-loading is not rendered)"
)
EXCLUDED_DECLARATIONS = {
    "BookingForm.vue | .booking-back-link | color: #6b7280": SHARED_CLASS_KEPT,
    "BookingForm.vue | .ghrm-error | color: #6b7280": DEAD_IN_THE_SPA,
    "BookingResourceDetail.vue | .ghrm-error | color: #6b7280": DEAD_IN_THE_SPA,
}
ADAPTER = "booking"
# Unscoped rules of these classes are checkout-wide: theme_checkout owns them.
CHECKOUT_WIDE_CLASSES = {
    "public-checkout",
    "loading-state",
    "error-state",
    "spinner",
    "checkout-content",
    "card",
    "checkout-actions",
    "requirements",
    "btn",
    "pay-button",
    "order-saved",
}
LEADING_CLASS = re.compile(r"^\.([\w-]+)")

# booking_success.html.j2 renders ``status-badge {{ success.status }}`` (BookingSuccess.vue
# ``:class="invoiceStatus"``): the lower-cased invoice statuses the SPA styles.
INVOICE_STATUS_CLASSES = {"paid", "authorized", "pending"}

# booking_runtime.js names the classes it toggles (``var SELECTED_CLASS = 'selected';``).
RUNTIME_CLASS_CONSTANT = re.compile(r"var \w+_CLASS = '([\w-]+)'")

needs_spa_checkouts = pytest.mark.skipif(
    not BOOKING_VIEWS.is_dir(),
    reason="the fe-user checkout is not next to vbwd-backend",
)


def _css_text(directory):
    return "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(directory.rglob("*.css"))
    )


def _ported_css():
    return _css_text(STYLESHEETS_DIRECTORY)


def _available_css():
    """What a booking page is styled by: theme_checkout's CSS, then booking's."""
    return _css_text(CHECKOUT_STYLESHEETS_DIRECTORY) + "\n" + _ported_css()


def _used_styled_classes():
    static_classes, prefixes = template_class_usage(TEMPLATES_DIRECTORY.rglob("*.j2"))
    static_classes |= script_classes(TEMPLATES_DIRECTORY.rglob("*.js"))
    static_classes |= INVOICE_STATUS_CLASSES
    for script in TEMPLATES_DIRECTORY.rglob("*.js"):
        static_classes |= set(
            RUNTIME_CLASS_CONSTANT.findall(script.read_text(encoding="utf-8"))
        )
    source_classes = set()
    for source in SOURCE_STYLE_FILES:
        source_classes |= rule_classes(
            vue_style_text(source.read_text(encoding="utf-8"))
        )
    return {name for name in source_classes if is_used(name, static_classes, prefixes)}


@needs_spa_checkouts
def test_all_source_style_files_exist():
    assert [str(path) for path in SOURCE_STYLE_FILES if not path.is_file()] == []


@needs_spa_checkouts
def test_every_used_styled_class_has_a_ported_rule():
    assert _used_styled_classes() - rule_classes(_available_css()) == set()


@needs_spa_checkouts
def test_every_ported_class_is_used_and_styled_in_the_spa():
    assert rule_classes(_ported_css()) - _used_styled_classes() == set()


def test_the_ported_css_styles_the_booking_pages():
    ported = rule_classes(_ported_css())

    for class_name in (
        "booking-catalogue",
        "booking-slot",
        "booking-form__field",
        "booking-resource-block",
        "confirmation-banner",
        "booking-cancel",
    ):
        assert class_name in ported


def test_the_checkout_wide_rules_live_in_theme_checkout_not_here():
    unscoped = {
        selector
        for selector, _property_name, _value in css_declarations(_ported_css())
        if (leading := LEADING_CLASS.match(selector))
        and leading.group(1) in CHECKOUT_WIDE_CLASSES
    }

    assert unscoped == set()


def test_theme_checkout_styles_the_shared_pay_page_classes():
    assert CHECKOUT_WIDE_CLASSES <= rule_classes(
        _css_text(CHECKOUT_STYLESHEETS_DIRECTORY)
    )


def test_the_ported_css_carries_no_hard_coded_colour():
    assert hard_coded_colours(_ported_css()) == []


@needs_spa_checkouts
def test_every_spa_colour_of_a_used_rule_is_ported_with_its_literal():
    unported = unported_spa_colours(
        SOURCE_STYLE_FILES, _available_css(), _used_styled_classes()
    )

    assert sorted(set(unported) - set(EXCLUDED_DECLARATIONS)) == []


@needs_spa_checkouts
def test_every_declaration_exclusion_is_still_an_unported_spa_colour():
    unported = unported_spa_colours(
        SOURCE_STYLE_FILES, _available_css(), _used_styled_classes()
    )

    assert set(EXCLUDED_DECLARATIONS) <= set(unported)


@needs_spa_checkouts
def test_every_booking_token_fallback_is_the_spa_literal():
    assert token_fallback_mismatches(SOURCE_STYLE_FILES, _ported_css(), ADAPTER) == []


def test_every_booking_token_is_documented_with_its_default_and_vice_versa():
    used = {
        token: sorted(fallbacks)
        for token, fallbacks in adapter_token_fallbacks(_ported_css(), ADAPTER).items()
    }
    documented = {
        token: [default] for token, default in documented_colour_tokens(ADAPTER).items()
    }

    assert used and used == documented


def test_every_booking_token_is_a_tokens_json_name():
    tokens = adapter_token_fallbacks(_ported_css(), ADAPTER)

    assert [name for name in tokens if not TOKEN_NAME_PATTERN.match(name)] == []
