"""S152-07c — booking pages get theme_checkout's checkout-wide CSS first, then booking's.

theme_booking declares theme_checkout as a dependency, so theme_checkout enables
(and contributes its stylesheet) first; the served theme.css therefore carries
the shared ``.card`` / ``.btn`` / ``.public-checkout`` rules before booking's own
rules, which keep the last word on the booking-scoped selectors.
"""
import re

STYLESHEET_PATH = "/_render/_theme/public/theme.css"
CHECKOUT_WIDE_RULES = (".public-checkout {", ".card {", ".btn {", ".spinner {")
FIRST_BOOKING_RULE = ".booking-catalogue {"
SCOPED_BOOKING_OVERRIDE = ".booking-success .card {"


def test_theme_css_serves_checkout_rules_before_booking_rules_before_tokens(client):
    response = client.get(STYLESHEET_PATH)

    css_text = response.get_data(as_text=True)
    assert response.status_code == 200
    booking_position = css_text.index(FIRST_BOOKING_RULE)
    for checkout_rule in CHECKOUT_WIDE_RULES:
        unscoped = [
            match.start()
            for match in re.finditer(f"^{re.escape(checkout_rule)}", css_text, re.M)
        ]
        assert len(unscoped) == 1, checkout_rule
        assert unscoped[0] < booking_position, checkout_rule
    assert booking_position < css_text.index(SCOPED_BOOKING_OVERRIDE)
    assert css_text.index(SCOPED_BOOKING_OVERRIDE) < css_text.rindex(":root")
