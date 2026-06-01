// friends-list island — live friend list with add-by-code + remove.

import { api } from '../api.js';

window.Alpine.data('friends-list', () => ({
  state: 'loading', // 'loading' | 'ready' | 'empty' | 'error'
  items: [],
  error: null,
  friendCode: '',
  addError: null,
  adding: false,

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
    return (this.error && this.error.message) || 'Could not load friends';
  },
  get hasAddError() {
    return this.addError !== null;
  },
  get addErrorMessage() {
    return (this.addError && this.addError.message) || 'Could not add friend';
  },

  async load() {
    if (!this.items.length) this.state = 'loading';
    try {
      this.items = await api.get(this.$root.dataset.src);
      this.state = this.items.length ? 'ready' : 'empty';
      this.error = null;
    } catch (e) {
      this.error = e;
      this.state = 'error';
    }
  },

  async add() {
    this.addError = null;
    this.adding = true;
    try {
      const friend = await api.post(this.$root.dataset.src, { friend_code: this.friendCode });
      this.items = [friend, ...this.items.filter((f) => f.id !== friend.id)];
      this.state = 'ready';
      this.friendCode = '';
    } catch (e) {
      this.addError = e;
    } finally {
      this.adding = false;
    }
  },

  async remove(id) {
    try {
      await api.delete(`${this.$root.dataset.src}${id}/`);
      this.items = this.items.filter((f) => f.id !== id);
      if (!this.items.length) this.state = 'empty';
    } catch (e) {
      this.error = e;
      this.state = 'error';
    }
  },
}));
