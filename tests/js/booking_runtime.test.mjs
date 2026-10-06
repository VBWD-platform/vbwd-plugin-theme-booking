// S152-09 — the themed booking pages' client-only rules (node --test).
// DRIFT NOTE — mirrored from vbwd-fe-user plugins/booking/booking:
//   slot pick / canProceed / check-out min / gallery thumbnails — views/BookingResourceDetail.vue
//   handleSubmit → store.pendingCheckout → /book/pay              — views/BookingForm.vue
//   BookingCheckout reads store.pendingCheckout                   — views/BookingCheckout.vue
//   "Try Again" router.back()                                    — views/BookingCancel.vue
// The pending booking lives in sessionStorage (the SPA keeps it in memory: lost on reload,
// never in the URL), posted as `pending` by every request of the pay island.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const RUNTIME_PATH = fileURLToPath(
  new URL('../../theme_booking/templates/booking/partials/booking_runtime.js', import.meta.url),
);
const PENDING_KEY = 'vbwd_booking_pending';

function node(attributes = {}, children = []) {
  const element = {
    attributes: { ...attributes },
    children,
    value: attributes.value || '',
    min: attributes.min || '',
    disabled: Object.prototype.hasOwnProperty.call(attributes, 'disabled'),
    classList: {
      names: new Set((attributes.class || '').split(' ').filter(Boolean)),
      toggle(name, on) {
        if (on) this.names.add(name);
        else this.names.delete(name);
      },
      contains(name) {
        return this.names.has(name);
      },
    },
    getAttribute: (name) => (name in element.attributes ? element.attributes[name] : null),
    setAttribute: (name, value) => (element.attributes[name] = String(value)),
    matches: (selector) => {
      const match = selector.match(/^\[([\w-]+)(?:="([^"]*)")?\]$/);
      return Boolean(match) && (match[2] === undefined ? match[1] in element.attributes : element.attributes[match[1]] === match[2]);
    },
    querySelectorAll: (selector) => {
      const found = [];
      const visit = (current) =>
        current.children.forEach((child) => {
          if (child.matches(selector)) found.push(child);
          visit(child);
        });
      visit(element);
      return found;
    },
    querySelector: (selector) => element.querySelectorAll(selector)[0] || null,
    closest: (selector) => {
      for (let current = element; current; current = current.parent) {
        if (current.matches(selector)) return current;
      }
      return null;
    },
  };
  children.forEach((child) => (child.parent = element));
  return element;
}

function loadRuntime(stored = {}) {
  const listeners = {};
  const assigned = [];
  const session = { ...stored };
  let wentBack = 0;
  const context = {
    document: {
      readyState: 'complete',
      addEventListener: (type, listener) => (listeners[type] = listeners[type] || []).push(listener),
    },
    sessionStorage: {
      getItem: (key) => (key in session ? session[key] : null),
      setItem: (key, value) => (session[key] = String(value)),
      removeItem: (key) => delete session[key],
    },
    location: { assign: (url) => assigned.push(url) },
    history: { back: () => (wentBack += 1) },
    FormData: function FormData(form) {
      this.forEach = (callback) => form.fields.forEach(([name, value]) => callback(value, name));
    },
    JSON,
  };
  context.window = context;
  vm.createContext(context);
  const source = readFileSync(RUNTIME_PATH, 'utf8');
  vm.runInContext(source, context);
  vm.runInContext(source, context);
  const fire = (type, event) => listeners[type].forEach((listener) => listener(event));
  return { listeners, fire, session, assigned, wentBack: () => wentBack };
}

function event(target, extra = {}) {
  return { target, prevented: false, preventDefault() { this.prevented = true; }, ...extra };
}

function fixedSlotForm() {
  const free = node({ 'data-vbwd-booking-slot': '', 'data-start': '09:00', 'data-end': '09:30', class: 'booking-slot' });
  const other = node({ 'data-vbwd-booking-slot': '', 'data-start': '10:00', 'data-end': '10:30', class: 'booking-slot selected' });
  const full = node({ 'data-vbwd-booking-slot': '', 'data-start': '11:00', 'data-end': '11:30', class: 'booking-slot full', disabled: '' });
  const start = node({ 'data-vbwd-booking-start': '' });
  const end = node({ 'data-vbwd-booking-end': '' });
  const bookNow = node({ 'data-vbwd-booking-book-now': '', disabled: '' });
  const slots = node({ id: 'booking-slots' }, [start, end, free, other, full]);
  const form = node({ 'data-vbwd-booking-book': '' }, [slots, bookNow]);
  return { form, free, other, full, start, end, bookNow, slots };
}

test('installs once even when the partial is included several times', () => {
  const { listeners } = loadRuntime();

  assert.equal(listeners.click.length, 1);
  assert.equal(listeners.submit.length, 1);
});

test('picking a free slot selects it, fills start / end and enables Book Now', () => {
  const { fire } = loadRuntime();
  const { free, other, start, end, bookNow } = fixedSlotForm();

  fire('click', event(free));

  assert.equal(free.classList.contains('selected'), true);
  assert.equal(other.classList.contains('selected'), false);
  assert.equal(start.value, '09:00');
  assert.equal(end.value, '09:30');
  assert.equal(bookNow.disabled, false);
});

test('a full slot cannot be picked', () => {
  const { fire } = loadRuntime();
  const { full, start, bookNow } = fixedSlotForm();

  fire('click', event(full));

  assert.equal(start.value, '');
  assert.equal(bookNow.disabled, true);
});

test('a new slot list (another date) disables Book Now until a slot is picked again', () => {
  const { fire } = loadRuntime();
  const { free, slots, start, bookNow } = fixedSlotForm();
  fire('click', event(free));

  start.value = '';
  fire('htmx:afterSwap', { detail: { target: slots } });

  assert.equal(bookNow.disabled, true);
});

test('a flexible stay needs a check-out after the check-in, whose date is its minimum', () => {
  const { fire } = loadRuntime();
  const checkIn = node({ 'data-vbwd-booking-check-in': '', min: '2026-10-04' });
  const checkOut = node({ 'data-vbwd-booking-check-out': '', min: '2026-10-04' });
  const bookNow = node({ 'data-vbwd-booking-book-now': '', disabled: '' });
  node({ 'data-vbwd-booking-book': '' }, [checkIn, checkOut, bookNow]);

  checkIn.value = '2026-11-02';
  fire('change', event(checkIn));
  assert.equal(checkOut.min, '2026-11-02');
  assert.equal(bookNow.disabled, true);

  checkOut.value = '2026-11-02';
  fire('input', event(checkOut));
  assert.equal(bookNow.disabled, true);

  checkOut.value = '2026-11-05';
  fire('input', event(checkOut));
  assert.equal(bookNow.disabled, false);
});

test('a thumbnail shows its image and becomes the active one', () => {
  const { fire } = loadRuntime();
  const image = node({ 'data-vbwd-booking-main-image': '', src: '/a.png' });
  const first = node({ 'data-vbwd-booking-thumb': '/a.png', class: 'booking-gallery__thumb active' });
  const second = node({ 'data-vbwd-booking-thumb': '/b.png', class: 'booking-gallery__thumb' });
  node({ 'data-vbwd-booking-gallery': '' }, [image, first, second]);

  fire('click', event(second));

  assert.equal(image.getAttribute('src'), '/b.png');
  assert.equal(second.classList.contains('active'), true);
  assert.equal(first.classList.contains('active'), false);
});

test('confirming the booking form keeps its fields and opens the pay page', () => {
  const { fire, session, assigned } = loadRuntime();
  const form = node({ 'data-vbwd-booking-form': '', action: '/booking/dr-smith/book/pay' });
  form.fields = [
    ['resource_slug', 'dr-smith'],
    ['start_at', '2026-11-02T09:00:00'],
    ['custom_fields.symptoms', 'Headache'],
    ['notes', 'E2E test booking'],
  ];
  const submit = event(form);

  fire('submit', submit);

  assert.equal(submit.prevented, true);
  assert.deepEqual(JSON.parse(session[PENDING_KEY]), {
    resource_slug: 'dr-smith',
    start_at: '2026-11-02T09:00:00',
    'custom_fields.symptoms': 'Headache',
    notes: 'E2E test booking',
  });
  assert.deepEqual(assigned, ['/booking/dr-smith/book/pay']);
});

test('other forms submit as usual', () => {
  const { fire, assigned } = loadRuntime();
  const submit = event(node({ action: '/elsewhere' }));

  fire('submit', submit);

  assert.equal(submit.prevented, false);
  assert.deepEqual(assigned, []);
});

test('every pay-island request carries the pending booking', () => {
  const { fire } = loadRuntime({ [PENDING_KEY]: '{"resource_slug":"dr-smith"}' });
  const button = node();
  node({ 'data-vbwd-booking-pending': '' }, [node({}, [button])]);
  const inside = { detail: { elt: button, parameters: { source: 'booking' } } };
  const outside = { detail: { elt: node(), parameters: {} } };

  fire('htmx:configRequest', inside);
  fire('htmx:configRequest', outside);

  assert.deepEqual(inside.detail.parameters, { source: 'booking', pending: '{"resource_slug":"dr-smith"}' });
  assert.deepEqual(outside.detail.parameters, {});
});

test('without a pending booking the island posts an empty one', () => {
  const { fire } = loadRuntime();
  const island = node({ 'data-vbwd-booking-pending': '' });
  const request = { detail: { elt: island, parameters: {} } };

  fire('htmx:configRequest', request);

  assert.equal(request.detail.parameters.pending, '');
});

test('a successful pay submit (HX-Redirect) forgets the pending booking', () => {
  const { fire, session } = loadRuntime({ [PENDING_KEY]: '{}' });
  const button = node();
  node({ 'data-vbwd-booking-pending': '' }, [button]);
  const response = (redirect) => ({
    detail: { elt: button, xhr: { getResponseHeader: (name) => (name === 'HX-Redirect' ? redirect : null) } },
  });

  fire('htmx:beforeOnLoad', response(null));
  assert.equal(PENDING_KEY in session, true);
  fire('htmx:beforeOnLoad', response('/pay/stripe?invoice=inv-1'));
  assert.equal(PENDING_KEY in session, false);
});

test('"Try Again" goes back like router.back()', () => {
  const { fire, wentBack } = loadRuntime();
  const link = node({ 'data-vbwd-history-back': '' });
  const click = event(link);

  fire('click', click);

  assert.equal(click.prevented, true);
  assert.equal(wentBack(), 1);
});
