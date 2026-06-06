// api.js — the client-side security spine for the islands (plan 06).
//
// Single fetch helper for every island. Responsibilities:
//   - same-origin credentials only (never `include` — no cross-origin cookie leak)
//   - X-CSRFToken on every unsafe method (satisfies SessionAuthentication; S-2)
//   - unwrap the {data, meta} envelope; throw ApiError({code,message,details,status})
//   - on 401, dispatch `pbl:auth-expired` (toast -> reload; never silent re-auth)
//   - escape() — the single XSS chokepoint for any manual DOM work
//
// No bundler: served as a native ES module by WhiteNoise; islands `import` it.

export class ApiError extends Error {
  constructor({ code, message, details, status, requestId }) {
    super(message || 'Request failed');
    this.name = 'ApiError';
    this.code = code || 'error';
    this.details = details || {};
    this.status = status;
    this.requestId = requestId;
  }
}

// Read the csrftoken cookie (CSRF_COOKIE_HTTPONLY=False makes this readable).
function csrf() {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : '';
}

// Pull the envelope apart: return `data` on 2xx, throw ApiError otherwise.
async function unwrap(res) {
  let body = null;
  try {
    body = await res.json();
  } catch (_) {
    /* non-JSON (proxy error page, etc.) — handled below */
  }

  const meta = (body && body.meta) || {};
  const requestId = meta.request_id;

  if (res.ok) {
    // Success envelope is { data, meta }. Be tolerant if `data` is absent.
    return body && 'data' in body ? body.data : body;
  }

  if (res.status === 401) {
    // Stop islands, prompt a clean re-auth. Never try to silently refresh.
    document.dispatchEvent(new CustomEvent('pbl:auth-expired', { detail: { requestId } }));
  }

  const err = (body && body.error) || {};
  throw new ApiError({
    code: err.code,
    message: err.message || `HTTP ${res.status}`,
    details: err.details,
    status: res.status,
    requestId,
  });
}

function send(url, method, body) {
  const opts = { method, credentials: 'same-origin', headers: {} };
  if (method !== 'GET' && method !== 'HEAD') {
    opts.headers['Content-Type'] = 'application/json';
    opts.headers['X-CSRFToken'] = csrf();
    if (body !== undefined) opts.body = JSON.stringify(body);
  }
  return fetch(url, opts).then(unwrap);
}

export const api = {
  get: (url) => send(url, 'GET'),
  post: (url, body) => send(url, 'POST', body),
  put: (url, body) => send(url, 'PUT', body),
  patch: (url, body) => send(url, 'PATCH', body),
  delete: (url, body) => send(url, 'DELETE', body),
};

// The single XSS chokepoint. Alpine `x-text` auto-escapes; use this ONLY when an
// island drops to manual DOM work. Never innerHTML an unescaped value.
export function escape(str) {
  const div = document.createElement('div');
  div.textContent = str == null ? '' : String(str);
  return div.innerHTML;
}

// Validate a URL from API data before binding to :href (plan 06, rule 5).
export function safeUrl(value) {
  if (value == null) return '#';
  const s = String(value);
  return /^https?:\/\//i.test(s) || s.startsWith('/') ? s : '#';
}
