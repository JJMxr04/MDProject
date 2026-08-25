// notifications island — the bell dropdown.
//
// Replaces the old vanilla notifications.js. Talks ONLY to /api/v1/notifications/
// via the shared api.js (CSRF, envelope, escaping). Renders loading/error/empty/
// ready states. The list returns only unread/uncleared notifications, so the
// dropdown is the "actionable" set. The owner can:
//   - mark one read   (PATCH .../<id>/)
//   - clear one       (POST  .../<id>/clear/)
//   - mark all read   (POST  .../mark-all-read/)
//   - clear all       (POST  .../clear-all/)
// A second mark/clear on an already-handled row deletes it server-side; here we
// just drop it from the local list. Rendered via x-text (auto-escaped) — never
// x-html.
//
// CSP build note: directive expressions can only reference property/method NAMES
// (no operators, ternaries, OR function-call syntax). The Alpine CSP evaluator
// resolves an expression by splitting on "." and walking the scope, so
// `markRead(n.id)` / `clearAll()` are NOT valid — they throw "unable to
// interpret". Every condition is therefore a getter (isLoading/hasItems/...),
// and every @click is a BARE method name. x-on passes the DOM event as the
// argument, so per-item handlers read the id from the element's data-id
// attribute (bound with `:data-id="n.id"`, a plain dotted path the CSP build
// does allow) via `event.currentTarget.dataset.id`.

import { api } from '../api.js';

window.Alpine.data('notifications', () => ({
  state: 'loading', // 'loading' | 'ready' | 'empty' | 'error'
  items: [],
  error: null,

  init() {
    // First load on mount; the island-loader drives any polling via load().
    this.load();
  },

  // --- getters the CSP-build template references by name ---------------
  get isLoading() {
    return this.state === 'loading';
  },
  get isError() {
    return this.state === 'error';
  },
  get isEmpty() {
    return this.state === 'empty';
  },
  get hasItems() {
    return this.items.length > 0;
  },
  get count() {
    return this.items.length;
  },
  get errorMessage() {
    return (this.error && this.error.message) || 'Could not load notifications';
  },

  // --- behavior --------------------------------------------------------
  async load() {
    // Only show the skeleton on the first fetch (nothing yet) — not on polls.
    if (!this.items.length) this.state = 'loading';
    try {
      this.items = await api.get(this.$root.dataset.src); // /api/v1/notifications/
      this.state = this.items.length ? 'ready' : 'empty';
      this.error = null;
    } catch (e) {
      this.error = e;
      this.state = 'error';
    }
  },

  // Tell other islands (e.g. the dashboard stats card) that the unread set
  // changed so their badge counts can refresh without waiting for the poll.
  _announceChange() {
    window.dispatchEvent(new CustomEvent('notifications:changed'));
  },

  // Drop an item from the local list and fall back to the empty state.
  _drop(id) {
    this.items = this.items.filter((n) => n.id !== id);
    if (!this.items.length) this.state = 'empty';
    this._announceChange();
  },

  // Per-item handlers receive the DOM event (CSP build passes $event). The id
  // rides on the clicked element as data-id (bound via :data-id="n.id").
  _idFromEvent(event) {
    return event && event.currentTarget && event.currentTarget.dataset.id;
  },

  async markRead(event) {
    const id = this._idFromEvent(event);
    if (!id) return;
    try {
      // dataset.src is the collection URL; the item URL is <src><id>/.
      await api.patch(`${this.$root.dataset.src}${id}/`, {});
      this._drop(id);
    } catch (e) {
      this.error = e;
      this.state = 'error';
    }
  },

  async clear(event) {
    const id = this._idFromEvent(event);
    if (!id) return;
    try {
      await api.post(`${this.$root.dataset.src}${id}/clear/`, {});
      this._drop(id);
    } catch (e) {
      this.error = e;
      this.state = 'error';
    }
  },

  async markAllRead() {
    try {
      await api.post(`${this.$root.dataset.src}mark-all-read/`, {});
      this.items = [];
      this.state = 'empty';
      this._announceChange();
    } catch (e) {
      this.error = e;
      this.state = 'error';
    }
  },

  async clearAll() {
    try {
      await api.post(`${this.$root.dataset.src}clear-all/`, {});
      this.items = [];
      this.state = 'empty';
      this._announceChange();
    } catch (e) {
      this.error = e;
      this.state = 'error';
    }
  },
}));
