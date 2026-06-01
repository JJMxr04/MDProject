// matches-list island — read-only list of the requester's matches.

import { api } from '../api.js';

window.Alpine.data('matches-list', () => ({
  state: 'loading', // 'loading' | 'ready' | 'empty' | 'error'
  items: [],
  error: null,

  init() {
    this.load();
  },

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
    return (this.error && this.error.message) || 'Could not load matches';
  },

  async load() {
    if (!this.items.length) this.state = 'loading';
    try {
      const rows = await api.get(this.$root.dataset.src);
      this.items = rows.map((m) => ({
        id: m.id,
        match_state: m.match_state,
        match_type: m.match_type,
        start_date: m.start_date,
        end_date: m.end_date,
        player_1_name: (m.player_1 && m.player_1.username) || '—',
        player_2_name: (m.player_2 && m.player_2.username) || 'Awaiting player',
        winner_name: (m.winner && m.winner.username) || '',
      }));
      this.state = this.items.length ? 'ready' : 'empty';
      this.error = null;
    } catch (e) {
      this.error = e;
      this.state = 'error';
    }
  },
}));
