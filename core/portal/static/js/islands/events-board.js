// events-board island — read-only list of upcoming events.
//
// Consumes the legacy DRF endpoint GET /api/events?sport=<slug>, which returns
// page-number pagination {count, next, previous, results:[...]} — NOT the v1
// envelope. api.get() hands the body back as-is when there is no `data` key, so
// we read body.results here.

import { api } from '../api.js';

window.Alpine.data('events-board', () => ({
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
    return (this.error && this.error.message) || 'Could not load events';
  },

  async load() {
    if (!this.items.length) this.state = 'loading';
    try {
      const body = await api.get(this.$root.dataset.src);
      const rows = (body && body.results) || [];
      this.items = rows.map((e) => ({
        event_id: e.event_id,
        home_team_name: (e.home_team && e.home_team.name) || 'TBD',
        away_team_name: (e.away_team && e.away_team.name) || 'TBD',
        league_name: (e.league && e.league.name) || '',
        start_time: e.start_time,
        status: e.status || '',
        is_live: !!e.is_live,
      }));
      this.state = this.items.length ? 'ready' : 'empty';
      this.error = null;
    } catch (err) {
      this.error = err;
      this.state = 'error';
    }
  },
}));
