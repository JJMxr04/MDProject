# Implementation roadmap

Three phases, ordered by **dependency and risk**, not by difficulty. Each phase ends at a demoable state — you can stop after any phase and the portal still works.

Estimated effort assumes one full-time engineer; multiply by coordination tax for a team.

---

## Phase 1 — Quick wins (1–2 days)

Goal: fix the most visible pain, ship nothing that requires a migration, keep all existing URLs stable.

### 1.1 Hygiene pass (2 h)
- [ ] Delete `core/match/templates/portal/match/my_match_detail copy.html`.
- [ ] Delete `core/admin/templates/admin/test/base.hmtl.html` (already queued).
- [ ] Delete `staticfiles/css/portal/blog/` after confirming no template extends.
- [ ] Delete `core/event/templates/portal/event/forum_list.html`, `create_thread.html` (unused, reference nonexistent URLs).

### 1.2 Fake data seeder (3 h)
- [ ] Land `core/commands/management/commands/seed_portal.py` per `data/fake_data_plan.md`.
- [ ] Smoke-test against a fresh DB: `manage.py migrate && manage.py seed_portal`.
- [ ] Document dev creds in `README.md`.

*Ship gate: run `seed_portal` and confirm at least one tournament lands in each of `created / inprogress / completed / aborted`.*

### 1.3 Design tokens (2 h)
- [ ] Create `core/portal/static/css/portal/tokens.css` with the full token file from `design-system/design_system.md § 1`.
- [ ] Include it from `base_portal.html` and `base_admin.html`.
- [ ] No template changes yet — tokens are available but unused.

### 1.4 Shared partials (4 h)
Create these partials and deploy them in just-the-dashboard first so you catch bugs early:
- [ ] `_page_header.html`
- [ ] `_stat_card.html`
- [ ] `_empty_state.html`
- [ ] `_badge.html` + `portal_state` template tag
- [ ] `_avatar.html`

### 1.5 Replace the stub dashboard (4 h)
- [ ] Rewrite `core/portal/views/dashboard.py` per `templates/dashboard.md`.
- [ ] Rewrite `core/portal/templates/portal/dashboard/dashboard.html`.
- [ ] Ship with stat cards + "Needs your attention" only. "Recent activity" can show an empty state in Phase 1.

### 1.6 Replace `alert()` with `toast()` (2 h)
- [ ] Add `_toast_host.html` and `static/js/portal/toast.js`.
- [ ] Find-and-replace `alert(` in:
  - `core/match/templates/portal/match/public_match_list.html`
  - `core/user/templates/portal/user/friend_search.html`
  - `core/match/templates/portal/match/my_match_detail.html`

### 1.7 Consolidate pagination (1 h)
- [ ] Create `_pagination.html`.
- [ ] Replace bespoke `{% for page_num in page_range %}` blocks in 3 templates.

**End of Phase 1**: portal feels tangibly more "put together" — dashboard shows real data, no `alert()` dialogs, consistent pagination, seeder runs. Nothing breaks. No migrations.

---

## Phase 2 — Structural improvements (1–2 weeks)

Goal: make the shell consistent and redesign each list / detail page. Includes one small migration (Tournament `description` + `end_date`).

### 2.1 Shared shell (3 d)
- [ ] Build `portal/base_app.html` + sidebar + topbar (`components/components.md § Shell`).
- [ ] Migrate `base_portal.html` to extend `base_app.html` (keep the name for template back-compat).
- [ ] Migrate `admin/base_admin.html` the same way.
- [ ] Ensure the sidebar highlights the active section — write `portal_nav` template tag.
- [ ] Delete `core/portal/templates/portal/components/sidebar.html` (already deleted; confirmed).
- [ ] Remove duplicated nav templates.

### 2.2 List pages redesign (4 d)

For each list page:
1. Wrap contents in `_page_header.html`.
2. Replace the left-column filter div with `_filter_bar.html`.
3. Swap table class to `.table-ui`.
4. Replace every `onclick=window.location` with `<a class="table-ui__row-link">`.
5. Add `_empty_state.html` at the bottom of the `{% for %}` block.

Pages to touch:
- [ ] `my_match_list.html` — plus view tweaks to annotate `opponent` and `state`.
- [ ] `public_match_list.html` — plus `[+ Create match]` in header; remove hand-rolled modal, use `_modal.html`.
- [ ] `my_tournaments.html` — plus view tweaks to annotate `accepted_count`, `rounds_completed`, `rounds_total`.
- [ ] `invite_list.html` — fix inconsistent directory name too (`portl` → `portal`).

### 2.3 Tournament detail + true bracket (3 d)
- [ ] Rewrite `my_tournament_detail.html` per `templates/tournament_detail.md`.
- [ ] Implement CSS-only bracket.
- [ ] Annotate rounds in view with `winner_is_player_1/2`, `is_mine`.
- [ ] Round side panel via Bootstrap offcanvas.

### 2.4 Match detail tabs (2 d)
- [ ] Split current long scroll into 4 partials (overview / games / picks / tiebreaker).
- [ ] URL-driven active tab via `?tab=`.
- [ ] Move JS URL constants into `data-*` attributes.
- [ ] Sticky match header on scroll.

### 2.5 Profile reshape (2 d)
- [ ] Extract section templates per `templates/profile.md`.
- [ ] Add `/profile/security/` URL + view using Django's `PasswordChangeForm`.
- [ ] Avatar live preview (6-line JS snippet).

### 2.6 Tournament model additions (1 d)
- [ ] `Tournament.description = TextField(blank=True)`.
- [ ] `Tournament.end_date = DateTimeField(null=True, blank=True)`, populate via the existing `get_end_date()` logic on save.
- [ ] Data migration to backfill `end_date` for existing tournaments.
- [ ] Add `description` / `end_date` to the admin tournament detail template.

### 2.7 Invite directory rename (30 min)
- [ ] Rename `core/mail/templates/portl/` → `core/mail/templates/portal/`.
- [ ] Update `render(...)` paths in `core/mail/views/invite.py`.

**End of Phase 2**: the portal and admin share one shell, every list has consistent layout, tournament detail shows a real bracket, profile is tabbed.

---

## Phase 3 — Advanced polish (2–3 weeks)

Goal: things that require design judgement rounds, new models, or longer build time.

### 3.1 Recent activity feed (3 d)
- [ ] Introduce a minimal `Activity` model with a `user`, `verb`, `target_type`, `target_id`, `at` timestamp.
- [ ] Signal receivers in `core.match.signals`, `core.tournament.signals` that write `Activity` rows on state transitions.
- [ ] Dashboard "Recent activity" query reads from this table.
- [ ] Admin page at `/admin/activity/` listing system-wide feed.

### 3.2 Notifications preferences (2 d)
- [ ] `UserNotificationPrefs` one-to-one model.
- [ ] Profile → Notifications section wired.
- [ ] Honour prefs in existing email send paths (`core.mail` codepaths).

### 3.3 Bracket polish (3 d)
- [ ] CSS connector lines between match boxes.
- [ ] Smooth transitions when winners propagate after a round completes.
- [ ] "Share bracket" button — generates a public read-only URL with a long-lived slug.

### 3.4 Dashboard personalisation (3 d)
- [ ] First-run checklist fully wired (`flows/user_flows.md § Flow 8`).
- [ ] "Your next tournament" card shows a mini bracket with the user's highlighted path.
- [ ] Real trend values on stat cards (current vs prev 7-day window).

### 3.5 Admin consolidation (3 d)
- [ ] `/admin/dashboard/` uses the same stat-card + card-ui grid as the portal dashboard.
- [ ] Add `/admin/matches/` list + detail (analogous to tournaments).
- [ ] Staff-only actions on tournament detail: reseed, abort, force-complete.

### 3.6 Account management (2 d)
- [ ] Profile → Account section with deactivate + data export.
- [ ] Deactivation sets `is_active=False`, removes from friend searches, soft-deletes invites.
- [ ] Export: JSON dump of user + matches + tournament entries, emailed as an attachment.

### 3.7 Mobile polish (2 d)
- [ ] Sidebar off-canvas behaviour fully tested.
- [ ] Match detail action bar sticky bottom with proper safe-area handling.
- [ ] Filter bar collapses to a single `[Filters]` button under 640 px, opens as an offcanvas.

**End of Phase 3**: portal matches mid-tier SaaS products on polish. Every empty state, loading state, and error state has a deliberate treatment.

---

## Things deliberately out of scope

| Item | Why skipped |
| --- | --- |
| Full design-token refactor of existing CSS files | Expensive. Tokens are available via `tokens.css`; migrate files as you touch them, not in one big sweep. |
| Replacing Bootstrap | No payoff. BS5 is fine; the design system overrides what it needs. |
| Dark mode | No current need. Tokens are ready if the ask ever comes. |
| React / Vue rewrite | Django templates are doing the job. Add a sprinkle of vanilla JS where needed. |
| Tournament visibility (private/public) | Needs product decision first. Surface the question; don't ship a flag for its own sake. |

---

## Ship checklist template

For each template shipped, verify:

- [ ] Renders at 375 × 667 (mobile) without horizontal scroll.
- [ ] Tab-keyboard flow touches every interactive control.
- [ ] Every `<img>` has `alt`.
- [ ] Every `{% url %}` resolves (`manage.py check` passes + manual smoke).
- [ ] Empty state present for every iterable.
- [ ] No inline `<style>` > 10 lines.
- [ ] No `alert()` calls.
- [ ] Uses tokens from `tokens.css`, no raw hex.

---

## Sequencing dependencies

```
P1.3 tokens ──┬─▶ P1.4 partials ──┬─▶ P1.5 dashboard
              │                   │
              │                   ├─▶ P1.6 toasts
              │                   │
              └──▶ P2.1 shell ────┴─▶ P2.2 list pages ──▶ P2.3 tournament detail
                                                          │
                                                          └─▶ P2.4 match detail
                                                             │
                                                             └─▶ P3.x polish
```

Don't start Phase 2 shell migration until Phase 1.3 tokens are in place — otherwise the shell CSS will hardcode hexes that you'll rewrite later.
