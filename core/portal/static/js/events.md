# Custom-event registry (inter-island comms)

Islands never import one another (plan 06 — "No island imports another").
They coordinate through `document` custom events or URL state. Every event used
across islands is registered here so the contract is auditable in one place.

| Event | Dispatched by | Listened by | `detail` | Purpose |
|-------|---------------|-------------|----------|---------|
| `pbl:auth-expired` | `api.js` (on any 401), `island-loader.js` | toast/shell + loader | `{ requestId }` | Session expired — stop polling, toast, prompt reload. Never silent re-auth. |
| `pbl:refresh` | (future) any island/control | islands subscribed to it | `{ scope? }` | Ask listening islands to re-run `load()` (e.g. after a mutation elsewhere). |
| `pbl:filter-change` | (future) a filter control island | data islands | `{ key, value }` | Broadcast a filter/URL-state change. |

## Rules

- Namespacing: all events are prefixed `pbl:`.
- Payload in `event.detail`, always a plain object (never a DOM node or a
  function).
- A dispatcher must not assume any listener exists; a listener must not assume a
  specific dispatcher.
- New cross-island events MUST be added to this table in the same PR that
  introduces them.
