# Templates — Matches (list + detail + public)

Covers three pages that share the same shell and idioms:

- `/web/portal/match/me/` — `my_match_list.html`
- `/web/portal/match/public/` — `public_match_list.html`
- `/web/portal/match/<uuid>/` — `my_match_detail.html`

Public match detail (`public_match_detail.html`) follows the same pattern as the detail below.

---

## My Match List

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ page-header: "My matches"                      [+ New match]    │
├──────────────────────────────────────────────────────────────────┤
│ filter bar: [All] [Pending] [Live] [Completed]  [search] [date] │
├──────────────────────────────────────────────────────────────────┤
│ table:                                                            │
│   Opponent · Sport · Status · Start · →                          │
│                                                                   │
│ or empty state:                                                   │
│   "No matches yet. Create a public match or accept an invite."    │
├──────────────────────────────────────────────────────────────────┤
│ pagination                                                        │
└──────────────────────────────────────────────────────────────────┘
```

### View

Context contract:
- `page_obj` — paginated `Match` queryset, already annotated with `opponent` (the user who *isn't* `request.user`).
- `filter_form` — status, query, date range.
- `quick_filters` — list of `{label, value, is_active}` for the status pills.
- `new_match_url` — `reverse('core-portal:portal-create-public-match')`.

### Template

```django
{% extends "portal/base_app.html" %}
{% load static portal_state portal_qs %}

{% block title %}My matches{% endblock %}

{% block content %}
  {% include "portal/components/_page_header.html" with title="My matches" subtitle="Matches you've created or accepted." actions_include="portal/match/_list_actions.html" %}

  {% include "portal/components/_filter_bar.html" with form=filter_form quick_filters=quick_filters %}

  {% querystring_without_page as qs %}

  {% if page_obj.object_list %}
  <div class="card-ui">
    <table class="table-ui">
      <thead>
        <tr>
          <th>Opponent</th>
          <th>Sport</th>
          <th>Status</th>
          <th>Start</th>
          <th aria-label="Open"></th>
        </tr>
      </thead>
      <tbody>
        {% for match in page_obj %}
          <tr>
            <td>
              <a class="table-ui__row-link" href="{% url 'core-portal:portal-my-match-detail' match.id %}">
                <div class="opponent-cell">
                  {% include "portal/components/_avatar.html" with user=match.opponent size=32 %}
                  <span>{{ match.opponent.username }}</span>
                </div>
              </a>
            </td>
            <td>{{ match.sport_label|default:"—" }}</td>
            <td>{% include "portal/components/_badge.html" with state=match.state %}</td>
            <td>{{ match.start_date|date:"M j, Y · g:i A" }}</td>
            <td class="text-end"><i class="bi bi-chevron-right text-muted"></i></td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% include "portal/components/_pagination.html" with page_obj=page_obj querystring=qs %}
  {% else %}
  {% include "portal/components/_empty_state.html" with
    icon="controller"
    title="No matches yet"
    body="Create a public match or accept an invite from a friend."
    action_label="Browse public matches"
    action_href="/web/portal/match/public/" %}
  {% endif %}
{% endblock %}
```

### View annotation

```python
# core/match/views/myMatchList.py
from django.db.models import Q, F, Case, When, Value, CharField

def my_match_list_view(request):
    user = request.user
    qs = Match.objects.filter(Q(player_1=user) | Q(player_2=user))

    qs = qs.annotate(
        opponent_id=Case(
            When(player_1=user, then=F("player_2")),
            default=F("player_1"),
        ),
    )
    # resolve opponent via select_related in template, or prefetch once:
    # qs = qs.select_related("player_1", "player_2")
    # then compute match.opponent in Python for each row:
    for m in qs:
        m.opponent = m.player_2 if m.player_1_id == user.id else m.player_1
    # …apply filters, paginate, render…
```

---

## Public Match List

Uses the same template structure. Columns:

| Column | Source | Notes |
| --- | --- | --- |
| Creator | `match.player_1.username` + avatar | |
| Sport | `match.sport_label` (if available) | |
| Created | `match.created` | relative ("5m ago") |
| Actions | `[Accept]` button | inline button, POST to `portal-accept-public-match` |

**Create Match button** is a primary CTA in the page header (not a side-bar button). Opens the shared `_modal.html`.

---

## Match Detail

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ breadcrumbs: Matches / vs Alex                                   │
├──────────────────────────────────────────────────────────────────┤
│ match header (sticky on scroll):                                  │
│   [You avatar]  YOU    vs    OPPONENT  [opp avatar]              │
│                 score        score                                │
│                           badge: state                           │
├──────────────────────────────────────────────────────────────────┤
│ TABS: [Overview] [Games] [Picks] [Tiebreaker?]                   │
├──────────────────────────────────────────────────────────────────┤
│ tab content                                                      │
│  ...                                                             │
├──────────────────────────────────────────────────────────────────┤
│ action bar (sticky bottom on mobile):                             │
│   [Submit picks]   [Decline match]                                │
└──────────────────────────────────────────────────────────────────┘
```

### Tabs

Driven by `?tab=overview|games|picks|tiebreaker`. Active tab's pane renders server-side; the other panes are *not* rendered (no hidden DOM). This keeps first paint fast and makes each tab a bookmarkable URL.

### Overview tab

- Start date / end date with `|date:"M j, Y · g:i A"`.
- Sport label, stake (if field exists).
- Rules summary (static copy for now).
- "How this works" 3-step list.

### Games tab

Reuses `_game_card.html` (existing in `core/match/templates/portal/match/_game_card.html`). Re-style only — keep view contract.

Each game card shows:
- Home team / Away team with logos.
- Sport + event date.
- Your pick (if made).
- Opponent's pick (only after lock time).

### Picks tab

Form to upload picks, per game in the match. Use `_field.html` per select. Replace the current form submission flow with:
1. POST via `fetch()` → server returns JSON `{success: true, updated_games: [...]}`.
2. On success: `toast('Pick saved.')`, update UI.
3. On error: `toast(msg, {variant: 'danger'})`.

### Tiebreaker tab

Shown only when `match.needs_tiebreaker` is true (context flag from view). Same form pattern.

### Action bar

Primary `[Submit picks]` is rendered only inside the Picks tab. "Decline match" lives in the Overview tab, not the sticky bar — de-risk accidental taps.

### Template (abbreviated)

```django
{% extends "portal/base_app.html" %}
{% load static portal_state %}

{% block title %}vs {{ match.opponent.username }}{% endblock %}

{% block content %}
  {% include "portal/components/_breadcrumbs.html" with crumbs=crumbs %}

  <header class="match-header card-ui">
    <div class="match-header__side">
      {% include "portal/components/_avatar.html" with user=request.user size=56 %}
      <span class="match-header__name">You</span>
      {% if match.my_score is not None %}<span class="match-header__score">{{ match.my_score }}</span>{% endif %}
    </div>
    <div class="match-header__center">
      <span class="match-header__vs">vs</span>
      {% include "portal/components/_badge.html" with state=match.state %}
    </div>
    <div class="match-header__side is-flipped">
      {% include "portal/components/_avatar.html" with user=match.opponent size=56 %}
      <span class="match-header__name">{{ match.opponent.username }}</span>
      {% if match.opp_score is not None %}<span class="match-header__score">{{ match.opp_score }}</span>{% endif %}
    </div>
  </header>

  <nav class="tabs" aria-label="Match sections">
    {% for tab in tabs %}
      <a class="tabs__tab {% if tab.key == active_tab %}is-active{% endif %}"
         href="?tab={{ tab.key }}" {% if tab.key == active_tab %}aria-current="page"{% endif %}>
        {{ tab.label }}{% if tab.badge %} <span class="badge-ui badge-ui--muted">{{ tab.badge }}</span>{% endif %}
      </a>
    {% endfor %}
  </nav>

  <section class="tab-panel">
    {% if active_tab == "overview" %}{% include "portal/match/_tab_overview.html" %}
    {% elif active_tab == "games" %}{% include "portal/match/_tab_games.html" %}
    {% elif active_tab == "picks" %}{% include "portal/match/_tab_picks.html" %}
    {% elif active_tab == "tiebreaker" %}{% include "portal/match/_tab_tiebreaker.html" %}
    {% endif %}
  </section>
{% endblock %}
```

### JS contract

Each tab that fetches data uses a single pattern:

```js
// static/js/portal/fetch_picks.js
document.querySelectorAll("[data-fetch-endpoint]").forEach((el) => {
  fetch(el.dataset.fetchEndpoint)
    .then(r => r.json())
    .then(data => renderInto(el, data))
    .catch(() => toast("Could not load picks.", { variant: "danger" }));
});
```

URL constants live in `data-*` attributes, not JS globals:

```html
<div class="picks" data-fetch-endpoint="{% url 'core-portal:portal-match-event-market' game.id %}"></div>
```

Deletes the `URL_EVENT_MARKETS`/etc. globals in `my_match_detail.html:216-220`.

---

## CSS

```css
.opponent-cell { display: flex; align-items: center; gap: var(--space-3); }

.match-header {
  display: grid; grid-template-columns: 1fr auto 1fr; align-items: center;
  padding: var(--space-5); margin-bottom: var(--space-5);
  gap: var(--space-5);
}
.match-header__side {
  display: flex; flex-direction: column; align-items: center; gap: var(--space-2);
}
.match-header__side.is-flipped { text-align: right; }
.match-header__score { font-size: var(--text-3xl); font-weight: var(--weight-bold); }
.match-header__center { display: flex; flex-direction: column; gap: var(--space-3); align-items: center; }
.match-header__vs { color: var(--text-secondary); font-weight: var(--weight-semibold); }

.tabs {
  display: flex; gap: var(--space-2); margin-bottom: var(--space-5);
  border-bottom: 1px solid var(--border-default);
}
.tabs__tab {
  padding: var(--space-3) var(--space-4); color: var(--text-secondary);
  text-decoration: none; font-weight: var(--weight-medium);
  border-bottom: 2px solid transparent; transition: color var(--motion-fast), border-color var(--motion-fast);
}
.tabs__tab:hover         { color: var(--text-primary); }
.tabs__tab.is-active     { color: var(--brand-blue-dark); border-bottom-color: var(--brand-blue-dark); }

.tab-panel { background: var(--surface-card); border: 1px solid var(--border-default); border-radius: 12px; padding: var(--space-5); }
```

---

## Delete list

- `core/match/templates/portal/match/my_match_detail copy.html` — stale duplicate.
- Inline `<style>` block in `public_match_list.html:7-50` — move to shared CSS.
- `alert()` calls in every JS block — replace with `toast()`.

---

## Done criteria

- [ ] Opponent column shows opponent (not "Player 1").
- [ ] Status pill is visible on every row.
- [ ] Match detail tabs are bookmarkable.
- [ ] No `alert()` / inline JS globals remain.
- [ ] Sticky match header survives on scroll without overlapping content.
