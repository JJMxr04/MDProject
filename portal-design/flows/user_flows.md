# User Flows

All flows assume the shared chrome defined in `design-system/design_system.md`: topbar + left sidebar, `portal-subnav` below the topbar when a section has sub-pages.

---

## Navigation structure (single source of truth)

```
Sidebar                           URL
────────────────────────────────  ───────────────────────────────────
🏠 Dashboard                      /web/portal/dashboard/
📅 Events                         /web/portal/event/upcoming-events/
🎮 Matches                        /web/portal/match/me/
   ├─ My matches                  /web/portal/match/me/
   └─ Public matches              /web/portal/match/public/
🏆 Tournaments                    /web/portal/tournament/me/
   └─ Tournament detail           /web/portal/tournament/<uuid>/
👥 Friends                        /web/portal/user/friends/search/
✉  Invites                       /web/portal/mail/invites/

Topbar right                      ─
• Bell (notifications)            (existing)
• Avatar dropdown
   ├─ Profile                     /web/portal/user/profile/
   ├─ Friends                     (duplicate of sidebar for discoverability)
   └─ Logout                      /logout/
```

Active state: sidebar item with path prefix match gets `aria-current="page"` and the `#FFE47A` background accent already defined for `.nav-pills .nav-link.active`.

---

## Flow 1 — Creating a tournament

**Who**: staff only today. The portal currently has no "create tournament" UI — tournaments are admin-created via Django admin. This flow covers creating from **admin** with a sane UX, not from portal.

**Entry**: `/admin/tournaments/` → `+ New tournament` button in the page header (to be added).

1. **Click** "New tournament" → `/admin/tournaments/new/`.
2. **Form** (single page, one card, no wizard):
   - Name · required text
   - Start date · datetime-local, default = next Saturday 18:00 local time
   - Max players · select [4, 8, 16, 32, 64, 128] (values that yield an integer `levels`)
   - Description · optional textarea (needs model field `description` — see `data/fake_data_plan.md`)
   - Visibility · radio `[Private] [Public]` (needs model field — Phase 2)
3. **Submit** →
   - Validate `max_players` is a power of 2. Server-side compute `levels = log2(max_players)` (manager already does this).
   - Save `Tournament` in `state='created'`.
   - Redirect to `/admin/tournaments/<id>/` (the detail page we already built).
4. **Detail page empty state** (currently missing): "This tournament has 0/N players. Invite players to begin." → "+ Invite player" opens modal.
5. **Invite player** → opens `/admin/tournaments/<id>/invite/` modal:
   - Autocomplete `<input>` searches `User.objects` by username/email.
   - Submit creates `InvitedPlayer` with `state='sent'`.
6. When `len(accepted_players) == max_players`, a **"Start bracket"** button appears → POSTs to `/admin/tournaments/<id>/start/` which calls `Tournament.objects.bracket_maker(tournament)`.
7. State transitions `created → inprogress`, detail page now shows the bracket.

**Status pills** (reuse the component in `admin/pages/tournament_detail.html`): `created=Upcoming`, `inprogress=In Progress`, `completed=Completed`, `aborted=Aborted`.

---

## Flow 2 — Managing a tournament (admin)

**Entry**: `/admin/tournaments/<id>/`.

1. **Tournament header** shows name, state pill, winner (if any), date, player count.
2. **Stat cards** (already built): Start date · Max players · Levels · Winner.
3. **Bracket section** shows rounds grouped by level with progression.
4. **Admin actions toolbar** (new, Phase 2), shown only for staff:
   - `[Advance round]` — manually mark a round complete (staff override).
   - `[Reseed players]` — shuffle seeds, only valid in `state='created'`.
   - `[Abort tournament]` — sets `state='aborted'`, confirm dialog.
   - `[Send reminders]` — triggers the existing `TournamentReminder` cron once.
5. **Player roster panel** (built): accepted vs invited side-by-side. Clicking a player in either list opens `/admin/users/<public_id>/`.

**Decision points**:
- If `state='created'` → admin can still invite / remove invites / start bracket.
- If `state='inprogress'` → admin can only observe, abort, or override round outcomes.
- If `state='completed'` → read-only, with an "Archive" action (Phase 3).

---

## Flow 3 — Viewing matches (portal player)

**Entry**: sidebar → **Matches**.

### My Matches (`/web/portal/match/me/`)

1. **Header**: `My Matches` title + `[+ New Match]` button (primary, yellow).
2. **Filter bar** (horizontal, above the list — not side-column):
   - Status tabs: `All · Pending · In Progress · Completed` (pill buttons, not select).
   - Search input (debounced 300 ms, updates on keypress).
   - Date range: single `datepicker` with "Past 7 days / Past month / All" preset chips.
3. **List**: table on desktop, card stack on mobile. Columns: `Opponent · Sport · Status · Start · →`.
4. **Row click** or `Enter` → `/web/portal/match/<id>/` (match detail). Entire row is an `<a>`.
5. **Empty state**: "No matches yet. Try a public match." with CTA → `/web/portal/match/public/`.

### Match Detail (`/web/portal/match/<id>/`)

1. **Match header** (sticky): opponent name + avatar, match state pill, scoreline if any.
2. **Tabs**:
   - **Overview** — start/end dates, stake/sport, how picks work (static copy once).
   - **Games** — list of games in this match. Each row uses the existing `_game_card.html` include but re-styled.
   - **Picks** — upload your pick (the current form), see your opponent's picks once locked.
   - **Tiebreaker** — shown only if `match.needs_tiebreaker`.
3. **Action buttons** pinned bottom-right on desktop, bottom-full-width on mobile.
4. **Loading state**: skeleton rows in each tab pane until `fetch()` resolves.
5. **Error state**: toast + retry button (replaces `alert()`).

### Public Matches (`/web/portal/match/public/`)

Identical shell to My Matches, but columns = `Creator · Sport · Created · [Accept]`.

- `[Accept]` button opens a confirm modal → POSTs to `portal-accept-public-match` → redirects to the new private match detail.

---

## Flow 4 — Viewing rounds / bracket (portal player)

**Entry**: sidebar → **Tournaments** → row click → Tournament Detail.

1. **Tournament header**: name + state + dates + winner.
2. **My position** panel (Phase 2): "You are in the quarterfinal. Next opponent: X."
3. **Bracket** rendered as a true CSS-grid bracket:
   - Rounds = columns, round N has 2ⁿ matches.
   - Each match-box is a vertical stack of two player rows.
   - Winner row gets `border-left: 4px solid #FFE47A` and `font-weight: 600`.
   - My matches get `outline: 2px solid #275d81`.
4. **Round click** → `/web/portal/tournament/round/<round_id>/` opens **Round Detail** in a side panel (offcanvas) on desktop, full-page on mobile.
5. **Round Detail side panel** shows: player avatars, match state, golden-game info, link to the underlying match detail.

---

## Flow 5 — Invitation lifecycle

**Sender path** (already partially built):
1. On **Friends** page, click `[Invite to Match]` next to a friend → modal → confirm → POST to `portal-create-public-match` with `type=private`.
2. Redirect to `invite-success` page → show "Sent! Your friend will see this under Invites."

**Recipient path**:
1. Red dot on bell icon when `Invite.objects.filter(player=user, state='sent')` is non-empty. Hover / click → dropdown shows 5 most recent.
2. Full list at `/web/portal/mail/invites/`.
3. Each invite card has two buttons: `[Accept]` (POST accept) and `[Decline]` (POST decline). Accept redirects to the new match.

---

## Flow 6 — Friends

(Flow is mostly working. Simplifications only.)

1. Sidebar → **Friends**.
2. Page has three regions:
   - **My friend code** (top, full width card) with copy button + regenerate button. Regenerate requires a confirm modal.
   - **Find friends** (left, 7 cols) — one combined input: "Enter friend code or username". If 8 chars alphanumeric → treat as code; else treat as search query.
   - **My friends** (right, 5 cols) — filterable list with remove + "Invite to match" per row.
3. Adding a friend: inline success banner (not `alert()`), friend appears in right column without full reload.

---

## Flow 7 — Profile / Account settings

**Entry**: avatar dropdown → **Profile**.

Two-panel layout:
- Left rail (sticky): **Profile · Security · Notifications · Account**.
- Right panel: the active section's form.

Each section is a Django `{% include %}`:
- **Profile** — first/last name, username, email, bio, avatar (the current form content, re-laid-out).
- **Security** — change password (Django form), list of active sessions (Phase 3).
- **Notifications** — email toggles, match-reminder cadence (Phase 3; needs a `UserPreference` model).
- **Account** — deactivate account, export data (Phase 3).

Avatar upload: show a live preview via a 2-line JS snippet on `<input change>`, not a separate form.

---

## Flow 8 — First-run / empty dashboard

New users see the dashboard immediately after registration (current redirect target is the portal).

1. Avatar + name + "Welcome, {{ first_name }}." as the `<h1>`.
2. Stat cards all read 0.
3. **"Get started" checklist** replaces the "Recent activity" panel until all items are done:
   - ☐ Complete your profile
   - ☐ Add your first friend (share your friend code)
   - ☐ Create or accept a match
   - ☐ Join a tournament
4. Each item links to the relevant page. Items that are done collapse with a checkmark.

Implementation note: compute the four booleans in the dashboard view and pass them in context — no client-side state.
