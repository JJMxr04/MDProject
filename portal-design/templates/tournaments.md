# Template — My Tournaments (list)

**URL**: `/web/portal/tournament/me/`
**Template**: `core/tournament/templates/portal/tournament/my_tournaments.html`
**View**: `core/tournament/views` → `my_tournaments`

Replaces the current left-column filter + centered table layout.

---

## Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ page-header:  "Tournaments"                [View: list | grid]  │
├─────────────────────────────────────────────────────────────────┤
│ filter-bar:  [All] [Upcoming] [In Progress] [Completed] [Aborted]│
│              [search] [start date] [end date]                   │
├─────────────────────────────────────────────────────────────────┤
│ list view (table)                                               │
│ ┌─Name────┬─Players─┬─Progress─┬─Start date─┬─State─┬─Actions─┐│
│ │ Spring  │ 16/16   │ ███▒▒    │ Apr 27     │ Upcom │ →       ││
│ │ …                                                           ││
│                                                                 │
│ grid view (toggle)                                              │
│ [Card] [Card] [Card] …   (3 cards per row on desktop, 1 on mob) │
├─────────────────────────────────────────────────────────────────┤
│ pagination                                                      │
└─────────────────────────────────────────────────────────────────┘
```

- **View toggle** persists via a `view=list|grid` query param.
- Default is list on ≥ 992 px, grid on mobile (tables become a scroll trap).

---

## Sections

### 1. Page header
`{% include "portal/components/_page_header.html" %}` with title `"Tournaments"` and actions block containing the view toggle. No "New tournament" button here — tournament creation is admin-only (see flow 1).

### 2. Filter bar
`{% include "portal/components/_filter_bar.html" %}`.

Status pill tabs are the primary filter — much clearer than a select. The tabs submit the form via GET so URLs are shareable.

### 3. List view
A `.table-ui` with these columns, each prioritised for what helps the user decide where to click:

| # | Column | Source | Notes |
| --- | --- | --- | --- |
| 1 | Name | `tournament.name` | The full cell is an `<a>` to detail. |
| 2 | Players | `tournament.player_set.count / tournament.max_accepted_players` | "8 / 16". |
| 3 | Progress | computed: rounds completed / total rounds | Render as a mini progress bar. |
| 4 | Start date | `tournament.start_date\|date:"M j, Y"` | Relative phrasing ("in 3 days") for near-future. |
| 5 | State | `{% include _badge.html with state=tournament.state %}` | |
| 6 | Actions | `<a>` → detail | Icon-only chevron. |

### 4. Grid view
One card per tournament. The card is a link; card content repeats the columns above vertically.

### 5. Empty state
`{% include _empty_state.html with title="No tournaments yet" body="You're not in any tournaments. Check back when signups open." icon="trophy" %}`.

### 6. Pagination
`_pagination.html`, carrying over all filter querystring params.

---

## View changes

Rewrite the view to:
- Accept `status` (string, default `all`), `q` (search), `start_date`, `end_date`, `view` (list|grid).
- Filter `Tournament.objects.filter(player__player=user)` with `.distinct()`.
- Add `.annotate(rounds_completed=Count('rounds', filter=Q(rounds__completed=True)), rounds_total=Count('rounds'))`.
- Paginate at 20 / page.
- Return context `{page_obj, filter_form, quick_filters, view_mode, querystring}`.

---

## Template

```django
{% extends "portal/base_app.html" %}
{% load static portal_state portal_qs %}

{% block title %}Tournaments{% endblock %}

{% block content %}
  {% include "portal/components/_page_header.html" with title="Tournaments" subtitle="Your tournaments, past and present." actions_include="portal/tournament/_list_actions.html" %}

  {% include "portal/components/_filter_bar.html" with form=filter_form quick_filters=quick_filters %}

  {% querystring_without_page as qs %}

  {% if page_obj.object_list %}
    {% if view_mode == "grid" %}
      <section class="tournament-grid">
        {% for t in page_obj %}
          {% include "portal/tournament/_card.html" with tournament=t %}
        {% endfor %}
      </section>
    {% else %}
      <div class="card-ui">
        <table class="table-ui">
          <thead>
            <tr>
              <th>Name</th>
              <th>Players</th>
              <th>Progress</th>
              <th>Start date</th>
              <th>State</th>
              <th aria-label="Open"></th>
            </tr>
          </thead>
          <tbody>
            {% for t in page_obj %}
              <tr>
                <td class="fw-semibold">
                  <a class="table-ui__row-link" href="{% url 'core-portal:core-portal-tournament:portal-my-tournament-detail' t.id %}">
                    {{ t.name }}
                  </a>
                </td>
                <td>{{ t.accepted_count }} / {{ t.max_accepted_players }}</td>
                <td>
                  <div class="progress-thin" aria-label="{{ t.rounds_completed }} of {{ t.rounds_total }} rounds">
                    <div class="progress-thin__fill" style="width: {% widthratio t.rounds_completed t.rounds_total 100 %}%;"></div>
                  </div>
                  <small class="text-muted">{{ t.rounds_completed }}/{{ t.rounds_total }}</small>
                </td>
                <td>{{ t.start_date|date:"M j, Y" }}</td>
                <td>{% include "portal/components/_badge.html" with state=t.state %}</td>
                <td class="text-end">
                  <i class="bi bi-chevron-right text-muted" aria-hidden="true"></i>
                </td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    {% endif %}

    {% include "portal/components/_pagination.html" with page_obj=page_obj querystring=qs %}
  {% else %}
    {% include "portal/components/_empty_state.html" with icon="trophy" title="No tournaments match these filters." body="Try clearing the filters or browse upcoming events." %}
  {% endif %}
{% endblock %}
```

---

## `_card.html` (grid view)

```django
<a class="tournament-card" href="{% url 'core-portal:core-portal-tournament:portal-my-tournament-detail' tournament.id %}">
  <header class="tournament-card__header">
    <h3 class="tournament-card__title">{{ tournament.name }}</h3>
    {% include "portal/components/_badge.html" with state=tournament.state %}
  </header>
  <dl class="tournament-card__meta">
    <div><dt>Start</dt><dd>{{ tournament.start_date|date:"M j" }}</dd></div>
    <div><dt>Players</dt><dd>{{ tournament.accepted_count }}/{{ tournament.max_accepted_players }}</dd></div>
    <div><dt>Rounds</dt><dd>{{ tournament.rounds_completed }}/{{ tournament.rounds_total }}</dd></div>
  </dl>
</a>
```

---

## CSS

```css
.tournament-grid {
  display: grid; gap: var(--space-5);
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
}
.tournament-card {
  display: block; padding: var(--space-5);
  background: var(--surface-card); border: 1px solid var(--border-default);
  border-radius: 12px; text-decoration: none; color: inherit;
  transition: transform var(--motion-fast), box-shadow var(--motion-fast);
}
.tournament-card:hover { transform: translateY(-1px); box-shadow: 0 6px 12px rgba(17,24,39,.06); }
.tournament-card__header { display: flex; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-4); }
.tournament-card__title { margin: 0; font-size: var(--text-lg); }
.tournament-card__meta  { display: grid; grid-template-columns: repeat(3, 1fr); margin: 0; gap: var(--space-3); }
.tournament-card__meta dt { font-size: var(--text-xs); text-transform: uppercase; color: var(--text-secondary); letter-spacing: .04em; }
.tournament-card__meta dd { margin: 0; font-weight: var(--weight-semibold); }

.progress-thin { height: 4px; background: var(--surface-muted); border-radius: 2px; overflow: hidden; }
.progress-thin__fill { height: 100%; background: var(--brand-blue); }
```

---

## Done criteria

- [ ] Filter pills are keyboard-operable (tab + enter).
- [ ] Clicking a row or card navigates with a real href (no `onclick=location=`).
- [ ] Empty state shows for filters that return zero rows (distinct from "you have no tournaments").
- [ ] Table switches to horizontal scroll on < 768 px; no layout break.
- [ ] Progress column renders even when `rounds_total == 0` (show "—").
