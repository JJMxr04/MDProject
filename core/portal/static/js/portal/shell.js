/* Portal shell interactions: sidebar toggle, modal open/close, filter popovers. */
(function () {
  document.addEventListener('click', function (event) {
    var target = event.target;

    // Sidebar toggle (legacy desktop drawer — unused on mobile now)
    if (target.closest('[data-sidebar-toggle]')) {
      var sidebar = document.querySelector('.sidebar');
      if (sidebar) sidebar.classList.toggle('is-open');
    }

    // Mobile menu sheet (bottom-bar "More")
    if (target.closest('[data-mobile-menu-toggle]')) {
      var mm = document.querySelector('[data-mobile-menu]');
      if (mm) mm.classList.toggle('is-open');
    }
    // Close: explicit close button, backdrop, or tapping any nav link inside
    if (target.closest('[data-mobile-menu-close]') ||
        target.closest('.mobile-menu__nav a') ||
        target.closest('.mobile-menu__profilelink')) {
      var mmc = document.querySelector('[data-mobile-menu]');
      if (mmc) mmc.classList.remove('is-open');
    }

    // Modal: open via <a data-modal-open="#id">
    var opener = target.closest('[data-modal-open]');
    if (opener) {
      event.preventDefault();
      var id = opener.getAttribute('data-modal-open');
      var m = document.querySelector(id);
      if (m) m.classList.add('is-open');
    }

    // Modal: close via [data-modal-close] or backdrop click
    var closer = target.closest('[data-modal-close]');
    var modal = target.closest('[data-modal]');
    if (closer && modal) {
      modal.classList.remove('is-open');
    } else if (modal && target === modal) {
      modal.classList.remove('is-open');
    }

    // Filter popover (<details class="filter-pop">): close any open one when
    // the click lands outside it. A click on its own summary/panel is inside
    // the <details>, so it stays open (native toggle still handles open/close).
    document.querySelectorAll('details.filter-pop[open]').forEach(function (d) {
      if (!d.contains(target)) d.removeAttribute('open');
    });
  });

  // Auto-submit a form when a [data-autosubmit] control changes (e.g. a filter
  // <select>). Inline onchange handlers are blocked by the strict CSP
  // (script-src 'self', no unsafe-inline), so filters opt in via this attribute.
  document.addEventListener('change', function (e) {
    var el = e.target;
    if (el.matches && el.matches('[data-autosubmit]') && el.form) {
      el.form.requestSubmit ? el.form.requestSubmit() : el.form.submit();
    }
  });

  // ESC closes open modals and the mobile menu
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('[data-modal].is-open').forEach(function (m) {
        m.classList.remove('is-open');
      });
      var mm = document.querySelector('[data-mobile-menu].is-open');
      if (mm) mm.classList.remove('is-open');
      // Close filter popovers and return focus to their trigger.
      document.querySelectorAll('details.filter-pop[open]').forEach(function (d) {
        d.removeAttribute('open');
        var summary = d.querySelector('summary');
        if (summary) summary.focus();
      });
    }
  });
})();
