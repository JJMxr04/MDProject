/* Lightweight toast helper. Attached to window so legacy inline scripts can use it. */
(function () {
  function toast(message, opts) {
    var options = Object.assign({ variant: 'info', timeout: 4000 }, opts || {});
    var host = document.querySelector('.toast-host');
    if (!host) return;
    var el = document.createElement('div');
    el.className = 'toast-ui toast-ui--' + options.variant;
    el.textContent = message;
    el.setAttribute('role', 'status');
    host.appendChild(el);
    setTimeout(function () { el.remove(); }, options.timeout);
  }
  window.toast = toast;
})();
