/* Portal shell interactions: sidebar toggle, modal open/close. */
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
  });

  // ESC closes open modals and the mobile menu
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('[data-modal].is-open').forEach(function (m) {
        m.classList.remove('is-open');
      });
      var mm = document.querySelector('[data-mobile-menu].is-open');
      if (mm) mm.classList.remove('is-open');
    }
  });
})();
