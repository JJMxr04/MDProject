// notifications island — the bell dropdown (plan 06/07, Phase 1 pilot).
//
// Replaces the old vanilla notifications.js. Talks ONLY to /api/v1/notifications/
// via the shared api.js (CSRF, envelope, escaping). Renders loading/error/empty/
// ready states and lets the owner mark a notification read (PATCH .../<id>/ ->
// deletes it). Rendered via x-text (auto-escaped) — never x-html.
//
// CSP build note: directive expressions can only reference property/method NAMES
// (no operators/ternaries). So every condition the template needs is exposed here
// as a getter (isLoading/isError/isEmpty/hasItems/...) rather than inlined as
// `state === 'loading'`. This keeps the page at script-src 'self' (no eval).

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

  async markRead(id) {
    try {
      // dataset.src is the collection URL; the item URL is <src><id>/.
      await api.patch(`${this.$root.dataset.src}${id}/`, {});
      this.items = this.items.filter((n) => n.id !== id);
      if (!this.items.length) this.state = 'empty';
    } catch (e) {
      this.error = e;
      this.state = 'error';
    }
  },
}));
