# Template — Tournament Detail

**URL**: `/web/portal/tournament/<uuid>/`
**Template**: `core/tournament/templates/portal/tournament/my_tournament_detail.html`
**View**: `core.tournament.views.my_tournament_detail`

Replaces the current flat "list of matches per level" view with a true bracket visualisation plus a "your position" panel and roster.

---

## Layout

```
┌────────────────────────────────────────────────────────────────┐
│ breadcrumbs:  Tournaments / Spring Shootout                    │
├────────────────────────────────────────────────────────────────┤
│ page-header:  Name + state pill + share button                  │
├─────────────────────────┬──────────────────────────────────────┤
│ stat cards (4 wide)     │                                      │
│  Start · Players · Levels · Winner                             │
├────────────────────────────────────────────────────────────────┤
│ TABS: [Bracket] [Roster] [About]                                │
├────────────────────────────────────────────────────────────────┤
│ BRACKET TAB                                                     │
│                                                                 │
│  Level 3 (QF)   Level 2 (SF)   Level 1 (F)   Level 0 (Winner)  │
│  ┌──────────┐                                                   │
│  │ A vs B   │──┐                                                │
│  └──────────┘  │  ┌──────────┐                                  │
│  ┌──────────┐  ├──│ winA vB  │──┐                               │
│  │ C vs D   │──┘  └──────────┘  │                               │
│  ┌──────────┐                   │  ┌──────────┐                 │
│  │ E vs F   │──┐                ├──│ winner   │                 │
│  └──────────┘  │  ┌──────────┐  │  └──────────┘                 │
│  ┌──────────┐  ├──│ winE vH  │──┘                               │
│  │ G vs H   │──┘  └──────────┘                                  │
│                                                                 │
│ Scrolls horizontally on small screens.                          │
├────────────────────────────────────────────────────────────────┤
│ ROSTER TAB                                                      │
│   Accepted players grid + Invited players list                 │
├────────────────────────────────────────────────────────────────┤
│ ABOUT TAB                                                       │
│   Description, rules, organiser, dates.                        │
└────────────────────────────────────────────────────────────────┘
```

Tabs are URL-backed via `?tab=bracket|roster|about`. No JS tab-switching so content is indexable and link-shareable.

---

## Sections

### 1. Breadcrumbs
`_breadcrumbs.html` with `[{"label": "Tournaments", "href": ...}, {"label": tournament.name}]`.

### 2. Page header
Title = `tournament.name`; subtitle = start-date relative ("Starts in 3 days" / "Started Mar 14"). Right-side actions:
- `[Share]` copies tournament URL to clipboard.
- `[View as admin]` visible only to staff, deep-links to `/admin/tournaments/<uuid>/`.

### 3. Stat cards
Copy the four already in `admin/pages/tournament_detail.html`: Start · Max players · Bracket levels · Winner. Re-use `_stat_card.html`.

Add a 5th card when the viewer is a participant: **"Your position"** — `"Quarterfinal"` / `"Eliminated in Round X"` / `"Not yet started"` / `"Winner"`. Computed server-side.

### 4. Bracket tab (the important one)

Render rounds as columns. Each round column is a `grid-template-rows` stack where match-box vertical centres align to the midpoint of their two prev-rounds. This is pure CSS — no JS layout engine needed.

```django
<div class="bracket" role="region" aria-label="Tournament bracket">
  {% for level, rounds in rounds_by_level %}
    <ol class="bracket__level" aria-label="Level {{ level }} ({{ rounds|length }} rounds)">
      {% for r in rounds %}
        <li class="bracket-match {% if r.completed %}is-completed{% endif %} {% if r.is_mine %}is-mine{% endif %}">
          {% include "portal/tournament/_bracket_slot.html" with player=r.player_1 is_winner=r.winner_is_player_1 %}
          {% include "portal/tournament/_bracket_slot.html" with player=r.player_2 is_winner=r.winner_is_player_2 %}
          {% if r.match_id %}
            <a class="bracket-match__open" href="{% url 'core-portal:portal-my-match-detail' r.match_id %}"
               aria-label="Open match details">
              <i class="bi bi-arrow-right"></i>
            </a>
          {% endif %}
        </li>
      {% endfor %}
    </ol>
  {% endfor %}
</div>
```

`_bracket_slot.html`:

```django
<div class="bracket-slot {% if is_winner %}is-winner{% endif %}">
  {% if player %}
    {% include "portal/components/_avatar.html" with user=player.player size=24 %}
    <span class="bracket-slot__name">{{ player.player.username }}</span>
    {% if player.seed %}<span class="bracket-slot__seed">#{{ player.seed }}</span>{% endif %}
  {% else %}
    <span class="bracket-slot__tbd">TBD</span>
  {% endif %}
</div>
```

Level ordering note: the template iterates **from last level to level 0** (finals on the right, first round on the left). The existing view groups rounds already — reverse the iteration in Python:

```python
ordered = sorted(grouped_rounds.items(), key=lambda kv: -kv[0])
```

Add fields to each `round` in view code:
- `winner_is_player_1` = `round.winner_id == round.player_1_id`
- `winner_is_player_2` = `round.winner_id == round.player_2_id`
- `is_mine` = `round.player_1.player_id == request.user.id or round.player_2.player_id == request.user.id`
- `match_id` = `round.match_id`

### 5. Roster tab
Two sub-sections:
- **Accepted** players: a grid of avatar cards with username, seed, division.
- **Invited** players: list with badge showing `state`.

Reuse `admin/pages/tournament_detail.html` structure, but unified badges via `_badge.html`.

### 6. About tab
- Organiser (if a `created_by` FK is added in Phase 2).
- Description (needs new `Tournament.description` field).
- Rules (link / markdown).
- Dates: created, starts, ends (needs `end_date` field — see flagged bug).

If no description exists yet, render an empty state with "Organiser hasn't added a description."

---

## CSS — the bracket

A pure-CSS bracket using `gap` and `justify-content: space-around` per column. No JS.

```css
.bracket {
  display: flex; gap: var(--space-5);
  overflow-x: auto; padding: var(--space-4); min-height: 400px;
  background: var(--surface-card); border: 1px solid var(--border-default); border-radius: 12px;
}
.bracket__level {
  list-style: none; margin: 0; padding: 0;
  display: flex; flex-direction: column; justify-content: space-around;
  min-width: 200px; gap: var(--space-3);
}
.bracket-match {
  position: relative;
  display: flex; flex-direction: column; gap: 2px;
  padding: var(--space-3); background: var(--surface-muted);
  border: 1px solid var(--border-default); border-radius: 8px;
}
.bracket-match.is-mine     { outline: 2px solid var(--brand-blue-dark); }
.bracket-match.is-completed .bracket-slot:not(.is-winner) { opacity: .55; }

.bracket-slot {
  display: flex; align-items: center; gap: var(--space-2);
  padding: var(--space-2); border-radius: 6px;
  background: var(--surface-card);
}
.bracket-slot.is-winner {
  border-left: 4px solid var(--brand-yellow);
  font-weight: var(--weight-semibold);
}
.bracket-slot__name { flex: 1; font-size: var(--text-sm); }
.bracket-slot__seed { font-size: var(--text-xs); color: var(--text-secondary); }
.bracket-slot__tbd  { color: var(--text-secondary); font-style: italic; }

.bracket-match__open {
  position: absolute; right: var(--space-2); top: 50%; transform: translateY(-50%);
  width: 24px; height: 24px; display: grid; place-items: center;
  color: var(--brand-blue-dark); opacity: 0; transition: opacity var(--motion-fast);
}
.bracket-match:hover .bracket-match__open { opacity: 1; }
```

**Connector lines** (optional, Phase 3): ::after pseudo-elements on each match-box that draw a horizontal line to the next column. Skippable in Phase 1 — readability is already good without.

---

## View sketch

```python
from collections import defaultdict
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from core.tournament.models.tournament import Tournament, Player, InvitedPlayer


@login_required(login_url="/auth/login/")
def my_tournament_detail(request, tournament_id):
    tournament = get_object_or_404(Tournament, id=tournament_id)
    tab = request.GET.get("tab", "bracket")

    rounds = (tournament.rounds
              .select_related("player_1__player", "player_2__player",
                              "winner__player", "match")
              .order_by("level_num"))

    by_level = defaultdict(list)
    my_user_id = request.user.id
    for r in rounds:
        r.winner_is_player_1 = r.winner_id and r.winner_id == r.player_1_id
        r.winner_is_player_2 = r.winner_id and r.winner_id == r.player_2_id
        r.is_mine = any(p and p.player_id == my_user_id
                        for p in (r.player_1, r.player_2))
        r.match_id = r.match_id
        by_level[r.level_num].append(r)
    rounds_by_level = sorted(by_level.items(), key=lambda kv: -kv[0])

    my_position = _compute_my_position(rounds, request.user)

    accepted = (Player.objects.filter(tournament=tournament)
                .select_related("player"))
    invited = (InvitedPlayer.objects.filter(tournament=tournament)
               .select_related("player"))

    return render(request, "portal/tournament/my_tournament_detail.html", {
        "tournament": tournament,
        "rounds_by_level": rounds_by_level,
        "accepted_players": accepted,
        "invited_players": invited,
        "my_position": my_position,
        "active_tab": tab,
    })
```

---

## Edge cases

- **Tournament with no rounds yet** (state `created`): bracket tab shows empty state "Bracket will appear once the tournament starts." with current accepted-player count.
- **User not in the tournament**: `my_position` is `None`; no "Your position" card; bracket still renders with no `.is-mine` highlight.
- **Round with both players TBD**: both slots render as "TBD" and match-box is muted.
- **Winner already declared**: final round's winner slot is prominent; page adds a subtle confetti SVG header accent (`#FFE47A` gradient) when `tournament.state == 'completed'`.

---

## Done criteria

- [ ] Bracket reads left-to-right with finals on the right.
- [ ] Winning player in each match is visually distinct.
- [ ] Horizontal scroll works at 375 px with no overflow from the shell.
- [ ] Clicking a match-box opens the match detail with the `role="link"` semantics (not an onclick).
- [ ] Tabs work via URL param; deep link to `?tab=roster` lands on roster.
