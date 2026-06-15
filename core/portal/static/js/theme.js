/* Theme switcher: auto (follow OS) / light / dark.
 * Loaded blocking in <head> so the initial attribute is set before first
 * paint (no flash). CSP-safe: external file, no inline script.
 *
 *   auto  -> no data-theme attr; CSS prefers-color-scheme media query rules.
 *   light -> data-theme="light" (forces light even if OS is dark).
 *   dark  -> data-theme="dark"  (forces dark even if OS is light).
 */
(function () {
  var KEY = 'pbl-theme';
  var root = document.documentElement;

  function stored() {
    try { return localStorage.getItem(KEY) || 'auto'; } catch (e) { return 'auto'; }
  }
  function apply(mode) {
    if (mode === 'light' || mode === 'dark') root.setAttribute('data-theme', mode);
    else root.removeAttribute('data-theme');
  }

  // Initial paint (this runs in <head>).
  apply(stored());

  var ICON = { auto: 'bi-circle-half', light: 'bi-sun', dark: 'bi-moon-stars' };
  var LABEL = { auto: 'Auto', light: 'Light', dark: 'Dark' };

  function sync() {
    var m = stored();
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      var i = btn.querySelector('i');
      if (i) i.className = 'bi ' + ICON[m];
      var lbl = btn.querySelector('[data-theme-label]');
      if (lbl) lbl.textContent = LABEL[m];
      btn.setAttribute('title', 'Theme: ' + LABEL[m]);
      btn.setAttribute('aria-label', 'Theme: ' + LABEL[m] + ' — click to change');
    });
  }

  function cycle() {
    var order = ['auto', 'light', 'dark'];
    var next = order[(order.indexOf(stored()) + 1) % order.length];
    try { localStorage.setItem(KEY, next); } catch (e) {}
    apply(next);
    sync();
  }

  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-theme-toggle]')) { e.preventDefault(); cycle(); }
  });
  document.addEventListener('DOMContentLoaded', sync);
})();
