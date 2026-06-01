// island-loader.js — discovers islands, starts Alpine once, drives polling (plan 06/09).
//
// Islands are Alpine.data() components in /static/js/islands/<name>.js. The host
// markup carries data-island="<name>" (which component), data-src (endpoint), and
// optional data-refresh-interval (ms). This loader:
//   1. imports each island module (each calls Alpine.data(...) at load),
//   2. starts Alpine once,
//   3. polls any [data-refresh-interval] host by calling its component load():
//      visibility-gated, jittered +/-20%, exponential backoff on error,
//      stop on `pbl:auth-expired`.
//
// Polling lives here (DRY) so individual islands don't each re-implement it.
// Requires the Alpine CSP build (vendored, no eval) to be present as window.Alpine.

const BASE = '/static/js/islands/';
const MAX_BACKOFF = 5; // multiplier cap on the configured interval

let pollingStopped = false;
document.addEventListener('pbl:auth-expired', () => {
  pollingStopped = true; // freeze polling; the auth-expired toast drives a reload
});

function jitter(ms) {
  // +/-20% so a wave of islands doesn't sync into a thundering herd. Math.random
  // is fine here (jitter, not security).
  return ms * (0.8 + Math.random() * 0.4);
}

function uniqueIslandNames() {
  const names = new Set();
  document.querySelectorAll('[data-island]').forEach((el) => {
    const name = el.getAttribute('data-island');
    if (name) names.add(name);
  });
  return names;
}

async function importIslands(names) {
  await Promise.all(
    [...names].map((name) =>
      import(`${BASE}${name}.js`).catch((e) =>
        console.error(`[island-loader] failed to load island "${name}"`, e)
      )
    )
  );
}

function startPolling(host) {
  const interval = parseInt(host.getAttribute('data-refresh-interval'), 10);
  if (!Number.isFinite(interval) || interval <= 0) return;

  let backoff = 1;

  const tick = async () => {
    if (pollingStopped) return; // do not reschedule once auth expired
    // Only poll a visible tab/element — saves the server and the battery.
    const visible = document.visibilityState === 'visible' && host.offsetParent !== null;
    if (visible) {
      const component = window.Alpine && window.Alpine.$data ? window.Alpine.$data(host) : null;
      if (component && typeof component.load === 'function') {
        try {
          await component.load();
          backoff = 1; // success resets backoff
        } catch (_) {
          backoff = Math.min(backoff * 2, MAX_BACKOFF); // grow on error
        }
      }
    }
    schedule();
  };

  const schedule = () => {
    if (pollingStopped) return;
    setTimeout(tick, jitter(interval * backoff));
  };

  schedule();
}

async function boot() {
  const names = uniqueIslandNames();
  if (!names.size) return;

  await importIslands(names);

  if (window.Alpine && typeof window.Alpine.start === 'function') {
    window.Alpine.start();
  } else {
    console.error('[island-loader] window.Alpine missing — vendor the Alpine CSP build');
    return;
  }

  document.querySelectorAll('[data-refresh-interval]').forEach(startPolling);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
