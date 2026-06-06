// tournaments-list island — read-only list of the user's tournaments.

import { api } from '../api.js';

window.Alpine.data('tournaments-list', () => ({
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
    return (this.error && this.error.message) || 'Could not load tournaments';
  },

  async load() {
    if (!this.items.length) this.state = 'loading';
    try {
      const rows = await api.get(this.$root.dataset.src);
      this.items = rows.map((t) => ({
        id: t.id,
        name: t.name,
        description: t.description || '',
        start_date: t.start_date,
        end_date: t.end_date,
        state: t.state,
        levels: t.levels,
        player_count: (t.players && t.players.length) || 0,
        max_accepted_players: t.max_accepted_players,
      }));
      this.state = this.items.length ? 'ready' : 'empty';
      this.error = null;
    } catch (e) {
      this.error = e;
      this.state = 'error';
    }
  },
}));
