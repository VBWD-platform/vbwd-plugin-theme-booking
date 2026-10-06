/**
 * S152 walkthrough @theme_booking — a patient books on the themed pages: the booking
 * catalogue → the resource's detail page → a date and a free slot → the booking form
 * with the resource's custom fields → the pay page by invoice → the confirmation with
 * the booking details section (custom fields appear once the payment is booked).
 *
 * Seeds (admin API): a bookable resource with a weekday schedule and two custom fields,
 * and a fresh buyer. Afterwards the booking is cancelled and the buyer and resource are
 * deleted — or, while the booking plugin refuses that (see `cancelResourceBookings`),
 * the resource is deactivated.
 */
import { test, expect } from '@playwright/test';
import { uniqueSlug } from '@fe-user-e2e/frontend-mode/frontend-mode-support';
import {
  AdminSeeder,
  CONFIRMATION_URL_PATTERN,
  WalkthroughSteps,
  invoiceIdFromConfirmationUrl,
  loginInBrowser,
  skipUnlessThemeMode,
  waitForViewerRegions,
  type WalkthroughBuyer,
} from '../../../theme/tests/e2e/support/walkthrough-support';

const BOOKING_RESOURCES = '/api/v1/admin/booking/resources';
const BOOKING_FORM_SLUG = 'booking-form';
const MONDAY = 1;
const WORKING_DAY = [{ start: '09:00', end: '17:00' }];
const SYMPTOMS = 'Walkthrough: mild headache';
const BOOKING_NOTES = 'Walkthrough booking — please call before.';

/**
 * The booking plugin cannot remove what a booking leaves behind today (recorded in the S152
 * report): a user with a reservation is refused force-delete (409, `booking_reservation`
 * FK) and a resource with one answers 500 on DELETE. So the walkthrough cancels its
 * bookings and takes the resource off the catalogue when it cannot be deleted.
 */
async function cancelResourceBookings(seeder: AdminSeeder, resourceId: string): Promise<void> {
  const { bookings } = await seeder.send('GET', `/api/v1/admin/booking/bookings?resource_id=${resourceId}`);
  for (const booking of bookings) {
    await seeder.send('PUT', `/api/v1/admin/booking/bookings/${booking.id}`, { status: 'cancelled' });
  }
}

async function retireResource(seeder: AdminSeeder, resourceId: string): Promise<void> {
  if (!(await seeder.deleteOrWarn(`${BOOKING_RESOURCES}/${resourceId}`))) {
    await seeder.send('PUT', `${BOOKING_RESOURCES}/${resourceId}`, { is_active: false });
  }
}

/** The next Monday (never today) as YYYY-MM-DD, inside the seeded schedule. */
function nextMonday(): string {
  const today = new Date();
  const daysAhead = (MONDAY - today.getDay() + 7) % 7 || 7;
  const monday = new Date(today);
  monday.setDate(today.getDate() + daysAhead);
  return monday.toISOString().split('T')[0];
}

test.describe('Walkthrough @theme_booking — catalogue, detail, slot, form, pay, confirmation', () => {
  skipUnlessThemeMode(test);

  const steps = new WalkthroughSteps('theme_booking');
  const resourceName = uniqueSlug('Walkthrough Dr. Theme');
  let seeder: AdminSeeder;
  let resource: Record<string, any>;
  let buyer: WalkthroughBuyer;

  test.beforeAll(async () => {
    seeder = await AdminSeeder.open();
    resource = await seeder.send('POST', BOOKING_RESOURCES, {
      name: resourceName,
      slug: uniqueSlug('walkthrough-resource'),
      description: 'General practitioner — 30 minute consultations (walkthrough).',
      capacity: 1,
      slot_duration_minutes: 30,
      price: 50,
      price_unit: 'per_slot',
      availability: {
        lead_time_hours: 2,
        max_advance_days: 30,
        schedule: { mon: WORKING_DAY, tue: WORKING_DAY, wed: WORKING_DAY, thu: WORKING_DAY, fri: WORKING_DAY, sat: [], sun: [] },
      },
      custom_fields_schema: [
        { id: 'symptoms', label: 'Symptoms', required: true, type: 'text' },
        { id: 'insurance', label: 'Insurance ID', required: false, type: 'string' },
      ],
      config: { confirmation_mode: 'auto' },
      is_active: true,
    });
    seeder.onCleanup(() => retireResource(seeder, resource.id));
    buyer = await seeder.freshBuyer();
    // Runs before the buyer's force-delete: frees the slot even when that delete is refused.
    seeder.onCleanup(() => cancelResourceBookings(seeder, resource.id));
  });

  test.afterAll(async () => {
    await seeder?.cleanup();
  });

  test('a patient picks a slot, fills the form, pays by invoice and sees the booking @theme_booking', async ({ page }) => {
    await loginInBrowser(page, buyer);

    await page.goto('/booking');
    await expect(page.locator('[data-testid="booking-catalogue"]')).toBeVisible();
    await page.fill('[data-testid="booking-catalogue-search"]', resourceName);
    const card = page.locator(`[data-testid="booking-resource-card-${resource.slug}"]`);
    await expect(card).toBeVisible();
    await steps.themed(page, '01-catalogue');

    await card.click();
    await page.waitForURL(`**/booking/${resource.slug}`);
    await waitForViewerRegions(page);
    await page.locator('.booking-date-picker input[type="date"][hx-get]').fill(nextMonday());
    const freeSlot = page.locator('.booking-slot:not(.full)').first();
    await expect(freeSlot).toBeVisible();
    await freeSlot.click();
    await expect(page.locator('[data-vbwd-booking-book-now]')).toBeEnabled();
    await steps.themed(page, '02-slot-picked');
    await page.click('[data-vbwd-booking-book-now]');

    await page.waitForURL(new RegExp(`/${BOOKING_FORM_SLUG}/${resource.slug}`));
    await waitForViewerRegions(page);
    const fields = page.locator('.booking-form__field');
    await fields.filter({ hasText: 'Symptoms' }).locator('input').fill(SYMPTOMS);
    await fields.filter({ hasText: 'Insurance ID' }).locator('input').fill('WALK-123');
    await page.locator('textarea').first().fill(BOOKING_NOTES);
    await steps.themed(page, '03-booking-form');
    await page.click('.ghrm-cta-btn');

    await page.waitForURL(/\/book\/pay/);
    await page.fill('[data-testid="billing-first-name"]', 'Walk');
    await page.fill('[data-testid="billing-last-name"]', 'Patient');
    await page.fill('[data-testid="billing-street"]', '5 Clinic Way');
    await page.fill('[data-testid="billing-city"]', 'Frankfurt');
    await page.fill('[data-testid="billing-zip"]', '60311');
    await page.locator('[data-testid="billing-country"]').selectOption({ index: 1 });
    await page.locator('[data-testid="payment-method-invoice"]').click();
    await page.locator('[data-testid="terms-checkbox"] input[type="checkbox"]').check();
    await expect(page.locator('.pay-button')).toBeEnabled();
    await steps.themed(page, '04-pay-page');
    await page.click('.pay-button');

    await page.waitForURL(CONFIRMATION_URL_PATTERN);
    const confirmation = page.locator('[data-testid="checkout-confirmation"]');
    await expect(confirmation.locator('[data-testid="confirmation-banner"]')).toBeVisible();
    await expect(confirmation.locator('.confirmation-mono')).toHaveText(/^BK-/);
    const bookingSection = confirmation.locator('[data-confirmation-section="booking"]');
    await expect(bookingSection).toContainText(resourceName);
    await expect(bookingSection).toContainText(BOOKING_NOTES);
    await steps.themed(page, '05-confirmation-pending');

    await seeder.markInvoicePaid(invoiceIdFromConfirmationUrl(page.url()));
    await page.reload();
    // Like the SPA's BookingConfirmationDetails, the section lists custom fields by id.
    const customFields = bookingSection.locator('.booking-custom-fields');
    await expect(customFields).toContainText('symptoms');
    await expect(customFields).toContainText(SYMPTOMS);
    await steps.themed(page, '06-confirmation-paid');
  });
});
