// dashboard-stats island — three per-user counts as cards.

import { api } from '../api.js';

window.Alpine.data('dashboard-stats', () => ({
  state: 'loading', // 'loading' | 'ready' | 'error'
  stats: { active_matches: 0, pending_invites: 0, notifications: 0 },
  error: null,

  init() {
    this.load();
    // Refresh immediately when notifications are read/cleared elsewhere
    // (e.g. the navbar bell) instead of waiting for the next poll.
    this._onNotificationsChanged = () => this.load();
    window.addEventListener('notifications:changed', this._onNotificationsChanged);
  },

  destroy() {
    window.removeEventListener('notifications:changed', this._onNotificationsChanged);
  },

  get isLoading() {
    return this.state === 'loading';
  },
  get isError() {
    return this.state === 'error';
  },
  get isReady() {
    return this.state === 'ready';
  },
  get activeMatches() {
    return this.stats.active_matches;
  },
  get pendingInvites() {
    return this.stats.pending_invites;
  },
  get notifications() {
    return this.stats.notifications;
  },
  get errorMessage() {
    return (this.error && this.error.message) || 'Could not load stats';
  },

  async load() {
    if (this.state !== 'ready') this.state = 'loading';
    try {
      this.stats = await api.get(this.$root.dataset.src);
      this.state = 'ready';
      this.error = null;
    } catch (e) {
      this.error = e;
      this.state = 'error';
    }
  },
}));
