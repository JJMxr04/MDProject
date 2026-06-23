// Signup timezone auto-detect (timezone + clock design §2, Option A).
// Pre-selects the browser's IANA timezone on the signup form's <select> so the
// user usually doesn't have to touch it; they can still change it. If detection
// fails or the zone isn't in the list, the server default (UTC) stays selected.
// CSP-safe: external file, no inline script.
(function () {
  var select = document.querySelector('select[data-timezone-detect]');
  if (!select) return;
  var tz;
  try {
    tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch (e) {
    return;
  }
  if (!tz) return;
  for (var i = 0; i < select.options.length; i++) {
    if (select.options[i].value === tz) {
      select.selectedIndex = i;
      return;
    }
  }
})();
