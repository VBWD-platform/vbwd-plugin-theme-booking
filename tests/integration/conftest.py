"""Integration fixtures: a real ``create_app`` in theme mode with the booking stack.

Boot: email, cms, checkout, booking, stripe (the REAL domain plugins and their
public API), theme, theme_cms, theme_checkout (with its payment flows), theme_booking;
fe-user "cms", "checkout", "booking" and "stripe-payment" enabled. Data lives in
the shared ``*_test`` database, each test in a rolled-back transaction;
resources, payment methods and CMS pages are seeded through the admin HTTP APIs
(``booking.spec.ts`` seeds the same way). The stripe plugin reads its sandbox
config from theme_checkout's payment config-store overlay; the Stripe SDK is stubbed per
test at the outbound boundary only.
"""
import pytest

from plugins.theme_checkout.tests.integration.themed_stack import (
    ADMIN_USER,
    TEST_USER,
    bearer_of,
    rolled_back_test_data,
    themed_app,
)
from plugins.theme_checkout.tests.integration.payment.conftest import (
    PaymentPluginsEnabledStore,
)

BOOT_ORDER = (
    "email",
    "cms",
    "checkout",
    "booking",
    "stripe",
    "theme",
    "theme_cms",
    "theme_checkout",
    "theme_booking",
)
FE_USER_PLUGINS = ("cms", "checkout", "booking", "stripe-payment")


@pytest.fixture(scope="module")
def var_directory(tmp_path_factory):
    return tmp_path_factory.mktemp("theme-booking-var")


@pytest.fixture(scope="module")
def app(var_directory):
    with themed_app(var_directory, BOOT_ORDER, FE_USER_PLUGINS) as application:
        application.config_store = PaymentPluginsEnabledStore(application.config_store)
        yield application


@pytest.fixture
def db(app):
    with rolled_back_test_data(app) as database:
        yield database


@pytest.fixture
def client(app, db):
    return app.test_client()


@pytest.fixture
def bearer(client):
    return bearer_of(client, TEST_USER)


@pytest.fixture
def admin_headers(client):
    return bearer_of(client, ADMIN_USER)


@pytest.fixture
def cms(client):
    from plugins.theme_cms.tests.integration.cms_seed import CmsAdminSeeder

    return CmsAdminSeeder(client)
