/*
 * booking_runtime.js — the themed booking pages' client-only rules (S152-09), ES2019, inlined
 * by the booking widgets and the pay page (installs once):
 *   - a [data-vbwd-booking-slot] click picks that slot: selected class, the hidden start / end,
 *     Book Now enabled (BookingResourceDetail.vue canProceed); a new slot list re-checks it;
 *   - a flexible stay: Book Now only for a check-out after the check-in, whose date is the
 *     check-out's minimum;
 *   - [data-vbwd-booking-thumb] shows its image in the gallery (activeImageUrl);
 *   - submitting [data-vbwd-booking-form] keeps its fields in sessionStorage (the SPA's
 *     store.pendingCheckout — never the URL: the notes and fields may be personal) and opens
 *     the pay page; every request inside [data-vbwd-booking-pending] posts them as `pending`;
 *     a successful pay submit (HX-Redirect) forgets them;
 *   - [data-vbwd-history-back] goes back (router.back()).
 * Everything is delegated on document, so swapped islands and regions keep working.
 */
(function (window) {
  'use strict';
  if (window.VbwdBooking) {
    return;
  }

  var PENDING_KEY = 'vbwd_booking_pending';
  var PENDING_PARAMETER = 'pending';
  var REDIRECT_HEADER = 'HX-Redirect';
  var SELECTED_CLASS = 'selected';
  var ACTIVE_CLASS = 'active';
  var BOOK_FORM_SELECTOR = '[data-vbwd-booking-book]';
  var PENDING_HOLDER_SELECTOR = '[data-vbwd-booking-pending]';

  function closest(target, selector) {
    return target && target.closest ? target.closest(selector) : null;
  }

  function canBook(form) {
    var checkIn = form.querySelector('[data-vbwd-booking-check-in]');
    if (checkIn) {
      var checkOut = form.querySelector('[data-vbwd-booking-check-out]');
      return Boolean(checkIn.value && checkOut.value && checkOut.value > checkIn.value);
    }
    var start = form.querySelector('[data-vbwd-booking-start]');
    return Boolean(start && start.value);
  }

  function refreshBookNow(form) {
    var checkIn = form.querySelector('[data-vbwd-booking-check-in]');
    if (checkIn) {
      form.querySelector('[data-vbwd-booking-check-out]').min = checkIn.value || checkIn.min;
    }
    form.querySelector('[data-vbwd-booking-book-now]').disabled = !canBook(form);
  }

  function pickSlot(slot) {
    if (slot.disabled) return;
    var form = slot.closest(BOOK_FORM_SELECTOR);
    form.querySelectorAll('[data-vbwd-booking-slot]').forEach(function (other) {
      other.classList.toggle(SELECTED_CLASS, other === slot);
    });
    form.querySelector('[data-vbwd-booking-start]').value = slot.getAttribute('data-start');
    form.querySelector('[data-vbwd-booking-end]').value = slot.getAttribute('data-end');
    refreshBookNow(form);
  }

  function showImage(thumb) {
    var gallery = thumb.closest('[data-vbwd-booking-gallery]');
    gallery.querySelector('[data-vbwd-booking-main-image]').setAttribute('src', thumb.getAttribute('data-vbwd-booking-thumb'));
    gallery.querySelectorAll('[data-vbwd-booking-thumb]').forEach(function (other) {
      other.classList.toggle(ACTIVE_CLASS, other === thumb);
    });
  }

  function handleClick(event) {
    var slot = closest(event.target, '[data-vbwd-booking-slot]');
    if (slot) return pickSlot(slot);
    var thumb = closest(event.target, '[data-vbwd-booking-thumb]');
    if (thumb) return showImage(thumb);
    if (closest(event.target, '[data-vbwd-history-back]')) {
      event.preventDefault();
      window.history.back();
    }
  }

  function handleDateChange(event) {
    var form = closest(event.target, BOOK_FORM_SELECTOR);
    if (form) refreshBookNow(form);
  }

  function handleSlotsSwapped(event) {
    var form = closest(event.detail.target, BOOK_FORM_SELECTOR);
    if (form) refreshBookNow(form);
  }

  function formFields(form) {
    var fields = {};
    new window.FormData(form).forEach(function (value, name) {
      fields[name] = value;
    });
    return fields;
  }

  function keepPendingBooking(event) {
    var form = closest(event.target, '[data-vbwd-booking-form]');
    if (!form) return;
    event.preventDefault();
    window.sessionStorage.setItem(PENDING_KEY, JSON.stringify(formFields(form)));
    window.location.assign(form.getAttribute('action'));
  }

  function addPendingBooking(event) {
    if (closest(event.detail.elt, PENDING_HOLDER_SELECTOR) && event.detail.parameters) {
      event.detail.parameters[PENDING_PARAMETER] = window.sessionStorage.getItem(PENDING_KEY) || '';
    }
  }

  function forgetPendingOnRedirect(event) {
    if (!event.detail.xhr.getResponseHeader(REDIRECT_HEADER)) return;
    if (closest(event.detail.elt, PENDING_HOLDER_SELECTOR)) {
      window.sessionStorage.removeItem(PENDING_KEY);
    }
  }

  window.document.addEventListener('click', handleClick);
  window.document.addEventListener('input', handleDateChange);
  window.document.addEventListener('change', handleDateChange);
  window.document.addEventListener('htmx:afterSwap', handleSlotsSwapped);
  window.document.addEventListener('submit', keepPendingBooking);
  window.document.addEventListener('htmx:configRequest', addPendingBooking);
  window.document.addEventListener('htmx:beforeOnLoad', forgetPendingOnRedirect);

  window.VbwdBooking = Object.freeze({
    canBook: canBook,
    PENDING_KEY: PENDING_KEY
  });
})(window);
