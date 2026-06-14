// duel-builder island — "Duel a friend" in three taps (phase 14).
//
// Flow: pick a friend → pick an upcoming event → pick a two-way market side.
// Tapping a side POSTs the challenge. Reuses the friends API, the per-event
// outcomes endpoint, and the duel send endpoint. CSP build: every @click is a
// BARE method name and per-item data rides on :data-* attributes, read off
// event.currentTarget (no method(arg) calls — see api.js islands).

import { api } from '../api.js';

function marketLabel(m) {
  const cat = (m.category || '').replace('_', ' ');
  const nice = cat.charAt(0) + cat.slice(1).toLowerCase();
  if (m.line !== null && m.line !== undefined && m.line !== '') {
    return `${nice} ${m.line}`;
  }
  return nice;
}

window.Alpine.data('duel-builder', () => ({
  state: 'loading', // 'loading' | 'ready' | 'error'
  friends: [],
  events: [],
  selectedFriendId: '',
  selectedFriendName: '',
  selectedEventId: '',
  selectedEventLabel: '',
  duelMarkets: [],
  loadingSides: false,
  message: '',
  messageType: '', // 'success' | 'error'

  async init() {
    try {
      const [friends, eventsBody] = await Promise.all([
        api.get(this.$root.dataset.friendsUrl),
        api.get(this.$root.dataset.eventsUrl),
      ]);
      this.friends = friends || [];
      this.events = (eventsBody && eventsBody.items) || [];
      this.state = 'ready';
    } catch (e) {
      this.state = 'error';
    }
  },

  // --- getters the CSP template references by name ---------------------
  get isLoading() { return this.state === 'loading'; },
  get isError() { return this.state === 'error'; },
  get hasFriends() { return this.friends.length > 0; },
  get noFriends() { return this.friends.length === 0; },
  get hasEvents() { return this.events.length > 0; },
  get noEvents() { return this.events.length === 0; },
  get showFriendStep() { return !this.selectedFriendId; },
  get showEventStep() { return !!this.selectedFriendId && !this.selectedEventId; },
  get showSideStep() { return !!this.selectedFriendId && !!this.selectedEventId; },
  get hasMessage() { return !!this.message; },
  get isSuccess() { return this.messageType === 'success'; },
  get hasSides() { return this.duelMarkets.length > 0; },
  get noSides() { return !this.loadingSides && this.duelMarkets.length === 0; },

  // --- behavior --------------------------------------------------------
  selectFriend(event) {
    const el = event.currentTarget;
    this.selectedFriendId = el.dataset.id;
    this.selectedFriendName = el.dataset.name;
    this.message = '';
  },

  resetFriend() {
    this.selectedFriendId = '';
    this.selectedFriendName = '';
    this.resetEvent();
  },

  async selectEvent(event) {
    const el = event.currentTarget;
    this.selectedEventId = el.dataset.id;
    this.selectedEventLabel = el.dataset.label;
    this.message = '';
    await this.loadSides();
  },

  resetEvent() {
    this.selectedEventId = '';
    this.selectedEventLabel = '';
    this.duelMarkets = [];
  },

  async loadSides() {
    this.loadingSides = true;
    this.duelMarkets = [];
    try {
      const url = this.$root.dataset.outcomesUrl.replace(
        'EVENTID', encodeURIComponent(this.selectedEventId),
      );
      const body = await api.get(url);
      const markets = (body && body.event && body.event.markets) || [];
      this.duelMarkets = markets
        .map((m) => {
          const priced = (m.selections || []).filter(
            (s) => !s.suspended && s.odds && s.odds.decimal,
          );
          if (priced.length !== 2) return null;
          return {
            label: marketLabel(m),
            sides: priced.map((s) => ({
              selection_id: s.selection_id,
              label: s.label,
              odds: s.odds.american,
            })),
          };
        })
        .filter(Boolean);
    } catch (e) {
      this.message = 'Could not load this event — try another.';
      this.messageType = 'error';
    } finally {
      this.loadingSides = false;
    }
  },

  async sendDuel(event) {
    const selectionId = event.currentTarget.dataset.selectionId;
    if (!selectionId || !this.selectedFriendId || !this.selectedEventId) return;
    try {
      await api.post(this.$root.dataset.sendUrl, {
        event_id: this.selectedEventId,
        selection_id: selectionId,
        opponent_id: this.selectedFriendId,
      });
      this.message = `Challenge sent to ${this.selectedFriendName}! They have until kickoff to accept.`;
      this.messageType = 'success';
      // Reset back to the start for the next challenge.
      this.resetFriend();
    } catch (e) {
      this.message = (e && e.message) || 'Could not send that duel.';
      this.messageType = 'error';
    }
  },
}));
