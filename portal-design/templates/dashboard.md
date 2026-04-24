# Template — Dashboard

**URL**: `/web/portal/dashboard/`
**View**: `core/portal/views/dashboard.py::portal_dashboard`
**Template**: `core/portal/templates/portal/dashboard/dashboard.html`

Currently a stub ("This portal is currently under development"). This redesign turns it into the player's home base — at-a-glance status, what needs action, and fast jumps to the things they do most.

---

## Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ page-header: "Welcome, {{ first_name }}." + quick action [+ New] │
├──────────────────────────────────────────────────────────────────┤
│ row of 4 stat cards                                              │
│   Active matches   Upcoming tournaments   Pending invites   Friends │
├─────────────────────────────────────────┬────────────────────────┤
│ "Needs your attention" (2/3 width)      │ "Your next tournament" │
│                                         │ (1/3 width)            │
│  • 2 pending match invites  [Accept]    │                        │
│  • 1 tournament awaiting pick [Open]    │  Spring Shootout       │
│  • Friend request from X     [View]     │  Starts in 3 days      │
│                                         │  8/16 players          │
│                                         │  [View bracket]        │
├─────────────────────────────────────────┴────────────────────────┤
│ Recent activity (full width, 10 items)                            │
│   • You won round against Alex · 2h ago                          │
│   • Match with Sam ended · yesterday                             │
└──────────────────────────────────────────────────────────────────┘
```

On screens < 768 px: stat cards become 2×2, "Needs your attention" and "Your next tournament" stack.

---

## Sections

### 1. Page header
Uses `_page_header.html`. Title: `"Welcome, {{ first_name|default:username }}."` No subtitle (the page is the landing, it doesn't need to introduce itself).

Primary action is a dropdown button `[+ New]`:
- New match → `core-portal:portal-create-public-match` (opens modal).
- Invite a friend → `core-portal:friend_search`.

### 2. Stat cards (4 `_stat_card.html` includes)

| Card | Value | Trend | Href |
| --- | --- | --- | --- |
| Active matches | count of user's matches in non-terminal state | +N this week | `portal-my-match-list?status=in_progress` |
| Upcoming tournaments | user's tournaments in `created` or `inprogress` | — | `portal-my-tournaments?status=upcoming` |
| Pending invites | `Invite.objects.filter(player=user, state='sent').count()` | — | `invite-list` |
| Friends | `user.friends.count()` | +N this month | `friend_search` |

Each card is a clickable tile; the whole card is the click target.

### 3. "Needs your attention" panel
A prioritised to-do list of things that are blocking the user *or* blocking someone else.

Priority order:
1. Pending match invites (red urgency).
2. Tournament rounds where the user hasn't submitted a pick but the match started.
3. Friend requests (if/when feature lands).
4. Completed matches where the user hasn't acknowledged the result.

Each row renders as a `<li>` with an icon, text, and an inline action button. Empty state: "You're all caught up." with a soft-green check.

### 4. "Your next tournament" panel
The user's tournament with the nearest future `start_date`. If none, fall back to the most recent `inprogress`. Empty state: "Not competing yet. Browse tournaments."

Renders a compact tournament card: name, date, accepted/max, state badge, `[Open]` button.

### 5. Recent activity feed
Up to 10 events from the last 14 days, union of:
- Match state transitions (created / accepted / completed).
- Round wins/losses in tournaments the user is in.
- Friends added.

View-side: build a simple `activity` list on the server. Phase 3: dedicated `Activity` model with a signal receiver.

### 6. First-run checklist (conditional)
If `user.friends.count() == 0` **and** no matches **and** no tournaments, replace section 5 with the 4-item checklist from `flows/user_flows.md § Flow 8`.

---

## View

Rewrite `core/portal/views/dashboard.py`:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta

from core.match.models.match import Match
from core.tournament.models.tournament import Tournament, Player
from core.mail.models import Invite


@login_required(login_url="/auth/login/")
def portal_dashboard(request):
    user = request.user
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    active_matches = Match.objects.filter(
        player_1=user
    ).union(Match.objects.filter(player_2=user)).filter(
        end_date__isnull=True  # adjust to actual "in progress" predicate
    )

    upcoming = (Tournament.objects
                .filter(player__player=user, state__in=["created", "inprogress"])
                .order_by("start_date")
                .distinct())

    pending_invites = Invite.objects.filter(player=user, state="sent")

    stats = {
        "active_match_count": active_matches.count(),
        "upcoming_tournament_count": upcoming.count(),
        "pending_invite_count": pending_invites.count(),
        "friend_count": user.friends.count(),
    }

    todo = _compute_todo(user, pending_invites)
    next_tournament = upcoming.first()
    activity = _recent_activity(user, since=week_ago, limit=10)

    is_first_run = (stats["friend_count"] == 0 and
                    stats["active_match_count"] == 0 and
                    stats["upcoming_tournament_count"] == 0)

    return render(request, "portal/dashboard/dashboard.html", {
        "stats": stats,
        "todo": todo,
        "next_tournament": next_tournament,
        "activity": activity,
        "is_first_run": is_first_run,
        "checklist": _first_run_checklist(user) if is_first_run else None,
    })
```

The `_compute_todo`, `_recent_activity`, and `_first_run_checklist` helpers live next to the view.

---

## Template

```django
{% extends "portal/base_app.html" %}
{% load static portal_state %}

{% block title %}Dashboard{% endblock %}

{% block content %}
  {% include "portal/components/_page_header.html" with title="Welcome, "|add:request.user.first_name|default:request.user.username|add:"." actions_include="portal/dashboard/_new_actions.html" %}

  <section class="grid-stats" aria-label="Your stats">
    {% include "portal/components/_stat_card.html" with label="Active matches" value=stats.active_match_count icon="controller" href="/web/portal/match/me/?status=in_progress" %}
    {% include "portal/components/_stat_card.html" with label="Upcoming tournaments" value=stats.upcoming_tournament_count icon="trophy" href="/web/portal/tournament/me/" %}
    {% include "portal/components/_stat_card.html" with label="Pending invites" value=stats.pending_invite_count icon="envelope" href="/web/portal/mail/invites/" %}
    {% include "portal/components/_stat_card.html" with label="Friends" value=stats.friend_count icon="people" href="/web/portal/user/friends/search/" %}
  </section>

  <section class="grid-columns-2-1 gap-6 mt-6">
    <div class="card-ui">
      <header class="card-ui__header">
        <h2>Needs your attention</h2>
      </header>
      <ul class="todo-list">
        {% for item in todo %}
          <li class="todo-list__row">
            <i class="bi bi-{{ item.icon }} todo-list__icon"></i>
            <span class="todo-list__text">{{ item.text }}</span>
            <a href="{{ item.href }}" class="btn-ui btn-ui--secondary btn-ui--sm">{{ item.cta }}</a>
          </li>
        {% empty %}
          {% include "portal/components/_empty_state.html" with icon="check2-circle" title="You're all caught up." %}
        {% endfor %}
      </ul>
    </div>

    <div class="card-ui">
      <header class="card-ui__header"><h2>Your next tournament</h2></header>
      <div class="card-ui__body">
        {% if next_tournament %}
          {% include "portal/tournament/_mini_card.html" with tournament=next_tournament %}
        {% else %}
          {% include "portal/components/_empty_state.html" with icon="trophy" title="Not competing yet." body="Join a tournament to get started." action_label="Browse" action_href="/web/portal/tournament/me/" %}
        {% endif %}
      </div>
    </div>
  </section>

  {% if is_first_run %}
    {% include "portal/dashboard/_first_run_checklist.html" with checklist=checklist %}
  {% else %}
    <section class="card-ui mt-6">
      <header class="card-ui__header"><h2>Recent activity</h2></header>
      <ul class="activity-feed">
        {% for event in activity %}
          <li class="activity-feed__row">
            <i class="bi bi-{{ event.icon }}"></i>
            <span class="activity-feed__text">{{ event.text }}</span>
            <time datetime="{{ event.at|date:'c' }}" class="activity-feed__time">{{ event.at|timesince }} ago</time>
          </li>
        {% empty %}
          {% include "portal/components/_empty_state.html" with icon="clock-history" title="No activity yet." %}
        {% endfor %}
      </ul>
    </section>
  {% endif %}
{% endblock %}
```

---

## CSS additions (dashboard-specific)

All non-structural styling lives in `static/css/portal/dashboard.css` — loaded only on this page:

```css
.grid-stats        { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-5); }
.grid-columns-2-1  { display: grid; grid-template-columns: 2fr 1fr; }

.stat-card {
  display: flex; gap: var(--space-4); padding: var(--space-5);
  background: var(--surface-card); border: 1px solid var(--border-default); border-radius: 12px;
  text-decoration: none; color: inherit;
  transition: transform var(--motion-fast), box-shadow var(--motion-fast);
}
.stat-card:hover { transform: translateY(-1px); box-shadow: 0 6px 12px rgba(17,24,39,.06); }
.stat-card__icon { width: 48px; height: 48px; display: grid; place-items: center;
  background: var(--surface-muted); border-radius: 12px; font-size: 24px; color: var(--brand-blue); }
.stat-card__label { font-size: var(--text-sm); color: var(--text-secondary); }
.stat-card__value { font-size: var(--text-3xl); font-weight: var(--weight-bold); line-height: 1.1; }
.stat-card__trend.is-up   { color: var(--state-success); }
.stat-card__trend.is-down { color: var(--state-danger); }

@media (max-width: 900px) {
  .grid-stats       { grid-template-columns: repeat(2, 1fr); }
  .grid-columns-2-1 { grid-template-columns: 1fr; }
}
```

---

## Edge cases

- If the view times out for any single panel's query (e.g., `activity`), show the empty-state for that panel only — render everything else.
- `first_name` may be empty → fall back to `username`.
- User with 1000+ friends: friend count stays correct; no client-side cost (render-once number).
- JavaScript-disabled: every card link works via `<a href>` — no hidden-behind-JS behaviour.

---

## Done criteria

- [ ] No page load with empty content ("under development" is gone).
- [ ] First-run user sees the checklist, returning user sees activity feed.
- [ ] All four stat cards reflect real queries.
- [ ] Page renders at 375 × 667 (mobile) without horizontal scroll.
- [ ] Lighthouse a11y score ≥ 95.
