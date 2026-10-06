"""S152-09 — theme_booking's English catalog never drifts from the SPA's copy.

* Every message a template asks for (``_('…')``) and every key the Python code
  chooses is in ``translations/en.json``, with no unused entry.
* Every entry equals the SPA's English for the same key (fe-user
  ``plugins/booking/locales/en.json`` + core ``vue/src/i18n/locales/en.json`` for
  PriceBreakdown's ``price.*``), with ``%(name)s`` ≡ ``{name}`` and ``%%`` ≡ ``%``.
  Theme-only keys are BookingCheckout.vue's hard-coded English, and must appear
  there verbatim. The fe-user half skips without fe-user (plugin CI).
"""
import json
import re
from pathlib import Path

import pytest

from plugins.theme.tests.catalog_contract import translated_catalog_paths
from plugins.theme_booking.theme_booking import success
from plugins.theme_booking.theme_booking.plugin_paths import (
    TEMPLATES_DIRECTORY,
    TRANSLATIONS_DIRECTORY,
)

FE_USER_ROOT = Path(__file__).resolve().parents[4].parent / "vbwd-fe-user"
FE_USER_CATALOGS = (
    FE_USER_ROOT / "vue" / "src" / "i18n" / "locales" / "en.json",
    FE_USER_ROOT / "plugins" / "booking" / "locales" / "en.json",
)
BOOKING_CHECKOUT_VIEW = (
    FE_USER_ROOT / "plugins" / "booking" / "booking" / "views" / "BookingCheckout.vue"
)
THEME_ONLY_COPY = {
    "booking.checkout.finalPrice": "Final price with coupon:",
    "booking.checkout.youSaved": "You have saved:",
    "booking.checkout.requirements.signIn": "Please log in or create an account",
    "booking.checkout.requirements.paymentMethod": "Select a payment method",
    "booking.checkout.requirements.billingAddress": "Enter billing address",
    "booking.checkout.requirements.acceptTerms": "Accept the terms and conditions",
}
CODE_CHOSEN_KEYS = set(success.TITLE_KEYS.values()) | {
    success.DEFAULT_TITLE_KEY,
    success.MESSAGE_PAID_KEY,
    success.MESSAGE_PENDING_KEY,
}
TRANSLATION_CALL = re.compile(r"""_\(\s*'([A-Za-z0-9_.]+)'\s*[,)]""")


def _catalog():
    return json.loads((TRANSLATIONS_DIRECTORY / "en.json").read_text(encoding="utf-8"))


def _flatten(prefix, node):
    for key, value in node.items():
        if isinstance(value, dict):
            yield from _flatten(f"{prefix}{key}.", value)
        else:
            yield f"{prefix}{key}", value


def _template_keys():
    keys = set()
    for template in TEMPLATES_DIRECTORY.rglob("*.j2"):
        keys.update(TRANSLATION_CALL.findall(template.read_text(encoding="utf-8")))
    return keys


def _as_spa_message(value):
    return re.sub(r"%\((\w+)\)s", r"{\1}", value).replace("%%", "%")


def test_every_requested_message_is_in_the_catalog():
    missing = (_template_keys() | CODE_CHOSEN_KEYS) - set(_catalog())

    assert not missing, sorted(missing)


def test_the_catalog_has_no_unused_entries():
    unused = set(_catalog()) - _template_keys() - CODE_CHOSEN_KEYS

    assert not unused, sorted(unused)


def test_theme_only_copy_is_listed_with_its_value():
    catalog = _catalog()

    assert {key: catalog[key] for key in THEME_ONLY_COPY} == THEME_ONLY_COPY


def test_theme_only_copy_is_the_spa_hard_coded_english():
    if not BOOKING_CHECKOUT_VIEW.is_file():
        pytest.skip("fe-user is not next to vbwd-backend (plugin CI)")
    source = BOOKING_CHECKOUT_VIEW.read_text(encoding="utf-8")

    assert [copy for copy in THEME_ONLY_COPY.values() if copy not in source] == []


def test_every_entry_equals_the_spa_english():
    if not all(path.is_file() for path in FE_USER_CATALOGS):
        pytest.skip("fe-user is not next to vbwd-backend (plugin CI)")
    spa = {}
    for path in FE_USER_CATALOGS:
        spa.update(_flatten("", json.loads(path.read_text(encoding="utf-8"))))
    drifted = {
        key: (value, spa.get(key))
        for key, value in _catalog().items()
        if key not in THEME_ONLY_COPY and _as_spa_message(value) != spa.get(key)
    }

    assert not drifted, drifted


def _spa_translations(language):
    """The SPA's messages in ``language``, merged in the same order as English."""
    spa = {}
    for path in FE_USER_CATALOGS:
        localized = path.with_name(f"{language}.json")
        if localized.is_file():
            spa.update(_flatten("", json.loads(localized.read_text(encoding="utf-8"))))
    return spa


def test_every_translated_entry_equals_the_spa_translation():
    if not all(path.is_file() for path in FE_USER_CATALOGS):
        pytest.skip("fe-user is not next to vbwd-backend (plugin CI)")
    drifted = {}
    for catalog_path in translated_catalog_paths(TRANSLATIONS_DIRECTORY):
        spa = _spa_translations(catalog_path.stem)
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        for key, value in catalog.items():
            if _as_spa_message(value) != spa.get(key):
                drifted[f"{catalog_path.stem}:{key}"] = (value, spa.get(key))

    assert not drifted, drifted
