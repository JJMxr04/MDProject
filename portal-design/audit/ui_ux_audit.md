# Portal UI/UX Audit

Scope: every page reachable under `/web/portal/` plus the shared navbar chrome.
Source of truth: current state of `core/portal/`, `core/match/`, `core/tournament/`, `core/user/`, `core/event/`, `core/mail/` templates and their CSS.

Colors referenced throughout this document are existing project tokens. They are not changed — they are only assigned to roles. See `design-system/design_system.md`.

---

## Global chrome issues

### NO Global CSS
- lets consolidate the css thats repeated and use global css. 

### Layout inconsistency (critical)
- `base_portal.html` has only a topbar, no sidebar. Content is wrapped in `col-10 offset-2` inside a container-fluid — a 2-column left gutter that is wasted space, not a sidebar.
- `base_admin.html` uses a fixed 250 px left sidebar + topbar + `margin-left: 270px` main region.
- Result: the portal and admin feel like two separate products. A user moving from `/admin/tournaments/` to `/web/portal/dashboard/` loses their navigation mental model.
- **Fix**: adopt one shell layout (topbar + left sidebar) for both portal and admin. Portal content shifts into a 240 px sidebar, exactly mirroring admin.

### Navbar gradient fights the content
- `portal_main.css` applies `linear-gradient(to right, #3D7EAA, #FFE47A)` to the navbar.
- `portal_layout.css` applies the same gradient to the `body`.
- Double-gradient surfaces create a muddy mid-tone stripe where the navbar meets content.
- **Fix**: navbar keeps the gradient, body becomes flat neutral (`#F5F7FA`). The gradient becomes a signature element, not background noise.

### Dropdown UX is hover-only
- `navbar.css:65`: dropdowns open on `:hover`. Unreachable on touch devices without a kludge; also fires on accidental mouse-over.
- **Fix**: click-to-open with Bootstrap's `data-bs-toggle="dropdown"` (already partially wired in `notification_profile_navbar.html:5` but not consistently).

### Orphan assets
- `core/portal/templates/portal/components/sidebar.html` was deleted in an earlier pass but its *intent* (site-wide left nav) was never replaced.
- `staticfiles/css/portal/blog/*` references a blog feature that no longer exists.
- **Fix**: delete `staticfiles/css/portal/blog/` after confirming no template extends it.

### Typography is unset
- Every template inherits `font-family: Arial, sans-serif`. No scale (`h1` … `h6`) is defined — each page sets its own header sizes inline.
- **Fix**: define a type scale (see `design-system/design_system.md`) and drop inline h-tag overrides.

### No focus styles, no skip link, no ARIA landmarks
- Tab-navigating the portal is invisible — most interactive elements inherit default browser focus rings that the yellow buttons (`#FFE47E`) wash out.
- No `<main>`, `<nav aria-label>`, or skip-to-content link.
- **Fix**: add a 2 px `#275d81` focus ring on every `.btn`, `.nav-link`, `input`, `select`, `textarea`. Add semantic landmarks in `base_portal.html`.

---

## Per-page issues

### Dashboard — `core/portal/templates/portal/dashboard/dashboard.html`
A hard-coded "under development" message.
- **No data surfaced.** The user lands here after login and sees nothing actionable. Active match count, upcoming tournaments, pending invites, recent activity, friend count — all available via existing ORM queries, none are shown.
- **No empty state.** If a user genuinely has nothing, the page should still guide them (*"Create your first match"*).
- **Fix**: replace the stub with a 4-stat-card grid + "Needs your attention" panel + "Upcoming" panel + "Recent activity" panel. See `templates/dashboard.md`.

### My Matches — `core/match/templates/portal/match/my_match_list.html`
- **Filter sidebar is not a sidebar**: it's a left column that sits above the table on mobile because of the `.filter-and-matches` flex layout — filters then push the table 500 px down. Awful on mobile.
- **Table columns are low-signal**: Match ID (UUID), Player 1, Player 2, Start Date, End Date. The *user's own name* appears as "Player 1" or "Player 2" depending on who created the match — no opponent column.
- **No status column.** The state filter exists but state is never rendered in the row.
- **Search filter has no apply button on primary filter, only on date** — inconsistent.
- **`onclick="window.location=..."` on `<tr>`** — not keyboard-accessible. Cells are not inside an `<a>` tag.
- **Fix**: collapsible filter bar above the table (not side), columns = `Opponent | Sport | Status | Start | Actions`, wrap row in semantic `<a>` around the first cell.

### Public Matches — `core/match/templates/portal/match/public_match_list.html`
- **Two-column only** (`Match ID`, `Player 1`). Gives the user no reason to pick one match over another.
- **Create modal built by hand** with inline `<style>` injecting an `#loading-overlay` plus `style="display:none"` on the modal.
- Relies on `alert()` for success/error feedback — blocks the UI thread and feels like 2005.
- The "Search User" label is confusing — the box searches matches by text, not users.
- **Fix**: inline "Create Match" button becomes the primary CTA in the page header. Result rows show `Creator | Created | Stake/Sport | Actions`. Replace `alert()` with a toast partial.

### Match Detail — `core/match/templates/portal/match/my_match_detail.html`
- File has a sibling `my_match_detail copy.html` — delete the copy; it's 1000+ lines of stale JS.
- **No visual separation** between the match overview, the golden-game selector, and the upload-pick form. Everything is stacked in one long scroll.
- **URLs are templated into JS constants** (lines 216-220) to work around the fact that match IDs are only known at runtime. Fine, but belongs in a `data-url` attribute, not a JS global.
- **Fix**: tabbed layout (Overview / Games / Picks / Tiebreaker) rendered as a single template with `{% if active_tab == 'x' %}` blocks. Scoreline and opponent header stay pinned above the tabs.

### My Tournaments — `core/tournament/templates/portal/tournament/my_tournaments.html`
- **Same anti-pattern as My Matches** — filter column that becomes a modal-sized stack on mobile.
- **State filter relies on hidden form submit** via `onchange="this.form.submit()"` — re-submits the whole URL on every change, discards any other pending filters the user typed but hasn't submitted.
- Table has `Name | Start Date | State` — missing `Players (accepted/max)`, `Rounds completed`, and the user's position in the bracket.
- **Fix**: horizontal filter bar, card-grid view toggle, add progress column.

### Tournament Detail — `core/tournament/templates/portal/tournament/my_tournament_detail.html`
- The bracket loops over `grouped_rounds.items` and emits a flat stack of `.bracket-match` divs per level. **Not a bracket** — just a list per level.
- Each match card shows avatar + name + "Vs." + avatar + name + completed/in-progress + winner. But the avatars are styled with the same size and border regardless of winner. No visual signal for "this player advanced".
- **Clickable cards** use the same `onclick` pattern as match list — not keyboard-accessible.
- No breadcrumb back to "My Tournaments".
- **Fix**: proper bracket — rounds as columns, each next round aligned between its two prev rounds using CSS grid. Winners get a highlighted border (use `#FFE47A` accent).

### Round Detail — `core/tournament/templates/portal/round/my_round_detail.html`
- Missing avatars fall back to `placeholder.jpg` (line 14) — that file doesn't exist at that static path.
- "Start Date" and "End Date" print raw `datetime.__str__` (line 37-38) — `2026-04-24 03:00:00+00:00` style. No formatting.
- **No state indicators** for match status beyond "Winner: Not decided yet".
- **Fix**: use `|date:"M j, Y · g:i A"`, add a status pill, provide avatar fallbacks via initials.

### Profile — `core/user/templates/portal/user/user_profile_form.html`
- **Bare single-column form.** No avatar preview update on selection, no validation surfacing per field, no "Cancel" button.
- Fallback avatar is `https://robohash.org/1` — a hardcoded URL, not a static asset.
- Missing sections the user expects from a SaaS product profile: account settings, security (password change), notification preferences, linked accounts.
- **Fix**: two-panel layout — sidebar with section tabs (Profile / Security / Notifications / Account), right panel with the active section's form. Each section is its own `{% include %}`.

### Friends — `core/user/templates/portal/user/friend_search.html`
- The cleanest page in the portal; uses `.card` consistently. Still:
  - **Two separate search affordances** (friend-code form + a `<form method="get">`-style text search that doesn't exist) — the text search UI is implied by `search_results` but there's no input for it.
  - **Inline `<style>` block** (lines 227-308) duplicates the modal CSS used by Match List — extract to a shared component.
  - **Alerts via `alert()`** (line 315, 341, 345, 347).
- **Fix**: unify search into one input with a "paste code or search by username" hint. Move modal + loading overlay to `portal/components/_modal.html` + `_loading_overlay.html`.

### Upcoming Events — `core/event/templates/portal/event/upcoming-events-list.html`
- Not read in depth but the URL pattern (`core-portal:upcoming-events`) plus its detail route exist.
- Sits outside the portal navigation mental model — "News" dropdown is the only entry point and it's buried.
- **Fix**: move Upcoming Events to a top-level sidebar item once the sidebar exists.

### Invite List — `core/mail/templates/portl/notifications/invite/invite_list.html`
- Directory is misspelled (`portl/` not `portal/`). Django resolves it because it's an include path, but every developer reads this twice.
- **Fix**: rename `core/mail/templates/portl/` → `portal/` in a dedicated commit. Update `views/invite.py` render calls.

### Invite Success — same directory
- Single CTA button, no secondary action (e.g., "Invite another friend").
- **Fix**: add secondary "Back to friends" link.

---

## Missing states (catalogued)

| Page | Empty state | Loading state | Error state |
| --- | --- | --- | --- |
| Dashboard | ❌ | ❌ | ❌ |
| My Matches | text-only "No matches found" | ❌ | ❌ |
| Public Matches | text-only "No matches found" | DIY spinner overlay | `alert()` |
| Match Detail | ❌ | ❌ (JS fetches fire silently) | `alert()` |
| My Tournaments | ❌ (empty table renders no row) | ❌ | ❌ |
| Tournament Detail | ❌ when rounds is empty | ❌ | ❌ |
| Round Detail | "No round details available" | ❌ | ❌ |
| Profile | n/a | ❌ | form errors render raw `{{ form.non_field_errors }}` |
| Friends | "You haven't added any friends yet." | DIY spinner | alert + inline `<div class="alert">` |
| Invite List | unknown (not read) | ❌ | ❌ |

**Fix**: canonical `_empty_state.html`, `_loading.html`, `_error_banner.html` partials. See `components/components.md`.

---

## Inconsistencies catalog

| Concern | Variant A | Variant B | Variant C |
| --- | --- | --- | --- |
| Table row click | `onclick=window.location` (my_match_list) | same but with `.href` (my_tournaments) | no row click (public_match_list has it anyway) |
| Primary CTA | yellow `.btn-primary` (`#FFE47E` bg, black text) | Bootstrap default blue `.btn-primary` (friend_search) | raw `<button type="submit">` (my_match_list filter) |
| Modal | hand-rolled in public_match_list | hand-rolled in friend_search (slightly different) | none elsewhere |
| Toast / feedback | `alert()` | Django messages rendered inline | none (silent) |
| Empty state | raw `<p>` text | empty `<tr>` row | nothing |
| Avatar fallback | `https://robohash.org/1` | `'placeholder.jpg'` static path (broken) | no fallback, `<img>` shows broken image |
| Date formatting | `\|date:"F j, Y"` | `\|date:"Y-m-d H:i"` | raw `__str__` |
| Heading style | `<h1 class="dashboard-title">` custom | `<h1>` + external CSS | `<h2>` for sibling sections |

Each inconsistency is cheap to fix once — see `design-system/design_system.md` and `components/components.md`.

---

## Data under-utilisation

Data already in the database that is not surfaced anywhere in the portal:

- `User.bio`, `User.friend_code`, `User.created` (joined date) — only shown on friend search result, never on the user's own dashboard.
- `Tournament.winner`, `Tournament.final_round` — never linked to on the list page.
- `Round.completed`, `Round.winner` — shown only on detail, no roll-up on the list.
- `Player.seed`, `Player.division` — stored but never rendered.
- `InvitedPlayer.state` (sent/accepted/declined/expired) — only the word, no badge, no action.
- `Match.start_date` vs `Match.end_date` — rendered as raw timestamps with no relative phrasing ("in 3 days").

See `data/fake_data_plan.md` for how to generate believable fixtures, and `templates/*.md` for where each field should appear.
