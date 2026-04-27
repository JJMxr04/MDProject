# Hockey (NHL) Extension Plan

**Scope:** extend the existing unified odds system to support Ice Hockey — specifically NHL — with minimal disruption to the soccer + american-football codepaths. SofaScore sport id for ice hockey is **`4`**.

**Market coverage:** game-level and team-level markets only. **No player props.** (Consistent with the original odds-system plan — this extension does not reintroduce `PROPS_PLAYER`.)

**Builds on:**
- [odds-system-plan.md](odds-system-plan.md) — the 5-category taxonomy (`MONEYLINE` / `SPREAD` / `TOTAL` / `PROPS_GAME` / `PROPS_TEAM`), `MarketScope`, deterministic market ids.
- Existing code: [core/event/odds/taxonomy.py](../core/event/odds/taxonomy.py), [core/event/odds/normalize.py](../core/event/odds/normalize.py), [core/event/models/odds/](../core/event/models/odds/).

**Status:** implemented and smoke-tested end-to-end. See §10 for the live probe findings that drove a late-stage fix.

---

## 1. Overview

### What's changing
- **Four new scope values:** `P1`, `P2`, `P3`, `SHOOTOUT`. `OVERTIME` and `FULL_GAME` already exist and are reused.
- **Hockey-specific market types** (`NHL_*`) appended to the existing `type` column values — the column is already `CharField(48)`, no schema change.
- **Two new scope strings** mapped in `SCOPE_MAP`:
  - `"Match"` → `FULL_GAME` (this is what SofaScore actually returns for full-game hockey markets, **not** `"Full-time"` — verified on the live probe in §10).
  - `"Regulation"` → `FULL_GAME` (regulation-only 3-way ML sits on a specific `type` value).
- **Live-events fallback** in the event cron: when `/tournaments/get-scheduled-events?categoryId=4` returns an empty `events` list (observed on the current RapidAPI plan), the cron automatically falls back to `/tournaments/get-live-events?sport=ice-hockey`. Same call count, same shape payload.

### What's NOT changing
- `MarketCategory` — still 5 values. No `PROPS_PLAYER`.
- Deterministic market id format.
- REST endpoints or their filters. One new query param `scope_subject=game|team` is added (player-scope is defined in the helper but currently unreachable since no PROPS_PLAYER rows exist).
- Normalization pipeline shape — only taxonomy rows + a few classifier rules are added.
- Redis cache keys, freshness tiers, monthly counters.

### Budget impact
| Sport | Events tick | Monthly events-ingest cost |
|---|---|---|
| Soccer (1) — active | 2×/day | 60 |
| Basketball (2) — inactive | — | 0 |
| American football (63) — active | 2×/day | 60 |
| **Ice hockey (4) — active** | **2×/day** | **60** |
| **Total events** | | **180** |

Leaves **~320 calls/month** for user-triggered odds fetches, shared across active sports.

---

## 2. Hockey MarketSpec Definitions

New canonical `type` values. Each row corresponds to rows in `SOFASCORE_MARKET_MAP` (§3).

| `type` (canonical) | `category` | `kind_slug` | format | Notes |
|---|---|---|---|---|
| `NHL_MATCH_WINNER_INC_OT` | MONEYLINE | `ml` | 2-way (HOME/AWAY) | Includes OT + shootout. Default US-book ML. **Verified live.** |
| `NHL_MATCH_WINNER_REG` | MONEYLINE | `mlreg` | 3-way (HOME/DRAW/AWAY) | Regulation only. SofaScore uses `marketPeriod="Regulation"`. *Placeholder ID.* |
| `NHL_PUCK_LINE` | SPREAD | `spread` | 2-way, signed line | Standard ±1.5; alternate puck lines per-row. *Placeholder ID.* |
| `NHL_MATCH_GOALS` | TOTAL | `total` | 2-way (OVER/UNDER), line | Over/Under total goals. **Verified live** with line=6.5. |
| `NHL_PERIOD_WINNER` | MONEYLINE | `ml` | 3-way | Period-scoped. Uses `scope ∈ (P1, P2, P3)`. *Placeholder IDs.* |
| `NHL_PERIOD_TOTAL` | TOTAL | `total` | 2-way, line | Period total goals. *Placeholder IDs.* |
| `NHL_BTTS` | PROPS_GAME | `btts` | YES/NO | Both teams to score. *Placeholder ID.* |
| `NHL_FIRST_GOAL_SCORER_TEAM` | PROPS_GAME | `firstteam` | 3-way | `HOME` / `AWAY` / `NO_GOAL`. *Placeholder ID.* |

*"Placeholder ID"* = best-effort `provider_market_id` keyed to the stable SofaScore market ids observed in soccer. The ingest pipeline skips unknown rows gracefully, so shipping before validation is safe. To verify, spend one `get_match_odds` call on an in-season NHL game.

### Intentionally deferred
- `NHL_TEAM_TOTAL_GOALS`, `NHL_TEAM_POWER_PLAY_GOALS`, `NHL_TEAM_PENALTY_MINUTES` — team-level `PROPS_TEAM` markets. Add as rows to the taxonomy once we see their SofaScore `marketId` values live. The `subject_team` field on `Market` already exists.
- `NHL_OVERTIME_YES_NO`, `NHL_EMPTY_NET_GOAL`, `NHL_EXACT_SCORE` — more `PROPS_GAME` rows; same story.

---

## 3. SOFASCORE_MARKET_MAP

Appended to [core/event/odds/taxonomy.py](../core/event/odds/taxonomy.py). Key: `(sport_id, provider_market_id, market_period)`.

```python
# --- Ice hockey (4) ---
# SofaScore uses marketPeriod="Match" for full-game hockey markets
# (not "Full-time" like soccer). Period-scoped rows use "1st period" /
# "2nd period" / "3rd period" — not yet observed live but added for safety.

(4, 1,  "Match"):      MarketSpec("MONEYLINE",  "NHL_MATCH_WINNER_INC_OT",  "ml"),
(4, 60, "Regulation"): MarketSpec("MONEYLINE",  "NHL_MATCH_WINNER_REG",     "mlreg"),
(4, 17, "Match"):      MarketSpec("SPREAD",     "NHL_PUCK_LINE",            "spread"),
(4, 9,  "Match"):      MarketSpec("TOTAL",      "NHL_MATCH_GOALS",          "total"),

# Period-scoped (placeholders; real IDs TBD)
(4, 1,  "1st period"): MarketSpec("MONEYLINE",  "NHL_PERIOD_WINNER",        "ml"),
(4, 1,  "2nd period"): MarketSpec("MONEYLINE",  "NHL_PERIOD_WINNER",        "ml"),
(4, 1,  "3rd period"): MarketSpec("MONEYLINE",  "NHL_PERIOD_WINNER",        "ml"),
(4, 9,  "1st period"): MarketSpec("TOTAL",      "NHL_PERIOD_TOTAL",         "total"),
(4, 9,  "2nd period"): MarketSpec("TOTAL",      "NHL_PERIOD_TOTAL",         "total"),
(4, 9,  "3rd period"): MarketSpec("TOTAL",      "NHL_PERIOD_TOTAL",         "total"),

# Game props (placeholders)
(4, 5,  "Match"):      MarketSpec("PROPS_GAME", "NHL_BTTS",                  "btts"),
(4, 6,  "Match"):      MarketSpec("PROPS_GAME", "NHL_FIRST_GOAL_SCORER_TEAM","firstteam"),
```

### Naming inconsistencies handled
- `"Match"` period string instead of soccer's `"Full-time"` — absorbed in `SCOPE_MAP`.
- Hockey moneyline is 2-way (HOME/AWAY only) — no `"X"` choice, so the `NHL_MATCH_WINNER_INC_OT` classifier only handles `"1"` and `"2"`.
- Same `(marketId=1, period="Match")` sometimes appears **twice** in the payload with different fractional odds — different provider feeds aggregated by SofaScore. Current behaviour: `update_or_create` on the deterministic `market_id` collapses them and last-write-wins. Selections from both feeds accumulate under the same Market row (idempotent on `sourceId`). See §9.4 for the edge case.

---

## 4. SCOPE_MAP

Two maps serve two different axes.

### 4.1 `SCOPE_MAP` (period axis — existing, extended)
```python
SCOPE_MAP = {
    "Full-time":   "FULL_GAME",   # soccer / AF
    "1st half":    "H1",
    "2nd half":    "H2",
    "1st quarter": "Q1",
    "2nd quarter": "Q2",
    "3rd quarter": "Q3",
    "4th quarter": "Q4",
    "Overtime":    "OVERTIME",
    # --- hockey additions ---
    "Match":       "FULL_GAME",   # hockey full-game
    "1st period":  "P1",
    "2nd period":  "P2",
    "3rd period":  "P3",
    "Regulation":  "FULL_GAME",   # regulation-only 3-way ML
    "Shootout":    "SHOOTOUT",
}
```

### 4.2 `SUBJECT_SCOPE_BY_CATEGORY` (subject axis — new helper)
Your spec's `SCOPE_MAP` (player/team/game) is a derivation of the existing `MarketCategory`. Not a table to maintain — just a helper so the REST filter `?scope_subject=team` Just Works without fighting our existing naming.

```python
SUBJECT_SCOPE_BY_CATEGORY = {
    "MONEYLINE":   "game",
    "SPREAD":      "game",
    "TOTAL":       "game",
    "PROPS_GAME":  "game",
    "PROPS_TEAM":  "team",
}

def subject_scope(category: str) -> str:
    return SUBJECT_SCOPE_BY_CATEGORY.get(category, "game")
```

Worked examples against your spec:
```
moneyline         → "game"   (category=MONEYLINE)
team_total_goals  → "team"   (category=PROPS_TEAM)
overtime (yes/no) → "game"   (category=PROPS_GAME, type=NHL_OVERTIME_YES_NO)
```

---

## 5. JSON Refactor (Before → After)

### 5.1 BEFORE — real SofaScore payload (verified live, Edmonton vs Anaheim, event 15950232)

```json
{
  "eventId": 15950232,
  "markets": [
    {
      "marketId": 1, "marketName": "Full time", "marketGroup": "Home/Away",
      "marketPeriod": "Match", "structureType": 1,
      "isLive": true, "suspended": false,
      "choices": [
        { "name": "1", "fractionalValue": "5/9",  "sourceId": 998112700 },
        { "name": "2", "fractionalValue": "7/5",  "sourceId": 998112701 }
      ]
    },
    {
      "marketId": 1, "marketName": "Full time", "marketGroup": "Home/Away",
      "marketPeriod": "Match", "structureType": 1,
      "choices": [
        { "name": "1", "fractionalValue": "37/50", "sourceId": 998112710 },
        { "name": "2", "fractionalValue": "23/20", "sourceId": 998112711 }
      ]
    },
    {
      "marketId": 9, "marketName": "Match goals", "marketGroup": "Match goals",
      "marketPeriod": "Match", "structureType": 2, "choiceGroup": "7.5",
      "choices": [
        { "name": "Over",  "fractionalValue": "8/5",  "sourceId": 998112720 },
        { "name": "Under", "fractionalValue": "10/21","sourceId": 998112721 }
      ]
    }
  ]
}
```

Key observations from the probe:
- Full-game period is `"Match"`, not `"Full-time"`.
- Hockey ML is 2-way (no `"X"`).
- Two rows for the same `(marketId=1, marketPeriod="Match")` appear, reflecting multiple provider feeds.

### 5.2 AFTER — unified shape served to Flutter

```json
{
  "event_id": 15950232,
  "sport": "ice_hockey",
  "league": { "id": 132, "name": "NHL, Playoffs", "slug": "nhl-playoffs" },
  "home_team": { "id": 3671, "name": "Edmonton Oilers",   "short": "Oilers" },
  "away_team": { "id": 3670, "name": "Anaheim Ducks",     "short": "Ducks" },
  "start_time": "2026-04-23T02:30:00Z",
  "status": "inprogress",
  "is_live": true,
  "markets": [
    {
      "market_id": "evt-15950232-ml-ft",
      "category": "MONEYLINE",
      "type": "NHL_MATCH_WINNER_INC_OT",
      "scope": "FULL_GAME",
      "line": null, "side": "",
      "subject": null,
      "suspended": false,
      "last_updated": "…",
      "selections": [
        { "selection_id": 998112700, "type": "HOME", "odds": { "decimal": 1.56, "american": -180, "fractional": "5/9"  } },
        { "selection_id": 998112701, "type": "AWAY", "odds": { "decimal": 2.40, "american": 140,  "fractional": "7/5"  } },
        { "selection_id": 998112710, "type": "HOME", "odds": { "decimal": 1.74, "american": -135, "fractional": "37/50"} },
        { "selection_id": 998112711, "type": "AWAY", "odds": { "decimal": 2.15, "american": 115,  "fractional": "23/20"} }
      ]
    },
    {
      "market_id": "evt-15950232-total-ft-7_5",
      "category": "TOTAL",
      "type": "NHL_MATCH_GOALS",
      "scope": "FULL_GAME",
      "line": 7.5, "side": "",
      "selections": [
        { "selection_id": 998112720, "type": "OVER",  "odds": { "decimal": 2.60, "american": 160,  "fractional": "8/5"  } },
        { "selection_id": 998112721, "type": "UNDER", "odds": { "decimal": 1.48, "american": -210, "fractional": "10/21"} }
      ]
    }
  ]
}
```

Notes:
- Four selections on the moneyline = two provider feeds stacked. UI renders best-of or first-of based on product preference. Proper provider segregation (distinct `Market` rows per feed) is a future hardening pass.
- `sport: "ice_hockey"` — added to `SPORT_SLUG_MAP` in [serializers/event.py](../core/event/serializers/event.py) and `SPORT_ID_BY_SLUG` in [views/api/events.py](../core/event/views/api/events.py).

---

## 6. Data Model Updates

All additive. No breaking changes to existing rows.

### 6.1 `MarketCategory` — unchanged
Still 5 values: `MONEYLINE`, `SPREAD`, `TOTAL`, `PROPS_GAME`, `PROPS_TEAM`.

### 6.2 `MarketScope` — add P1/P2/P3/SHOOTOUT
```python
class MarketScope(models.TextChoices):
    FULL_GAME = "FULL_GAME"
    H1 = "H1"
    H2 = "H2"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    OVERTIME = "OVERTIME"
    PERIOD_N = "PERIOD_N"
    # --- hockey additions ---
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    SHOOTOUT = "SHOOTOUT"
```

### 6.3 `Market` model — unchanged
`subject_team` already exists for team-prop support.

### 6.4 Deterministic `market_id` — new scope slugs
```python
scope_slug = {
    "FULL_GAME": "ft", "H1": "h1", "H2": "h2",
    "Q1": "q1", "Q2": "q2", "Q3": "q3", "Q4": "q4",
    "OVERTIME": "ot", "PERIOD_N": "pn",
    "P1": "p1", "P2": "p2", "P3": "p3", "SHOOTOUT": "so",
}
```

### 6.5 Migration
One auto-generated `AlterField(model_name="market", name="scope", field=...)` to carry the new choice list. **Already applied** ([0002_alter_market_scope.py](../core/event/migrations/0002_alter_market_scope.py)).

---

## 7. Normalization Pipeline

Deltas only — everything not mentioned stays the same.

### 7.1 `build_market_id` — new scope slug entries
Covered in §6.4. No new kwarg.

### 7.2 `classify_choice` — hockey rules appended
```python
# inside classify_choice(spec, raw_name, home_team, away_team)

if spec.type in ("NHL_MATCH_WINNER_INC_OT", "NHL_PERIOD_WINNER"):
    if n == "1": return "HOME", home_team
    if n == "X": return "DRAW", "Draw"
    if n == "2": return "AWAY", away_team

if spec.type == "NHL_MATCH_WINNER_REG":
    if n == "1": return "HOME", home_team
    if n == "X": return "DRAW", "Draw (regulation)"
    if n == "2": return "AWAY", away_team

if spec.type == "NHL_PUCK_LINE":
    if home_team and home_team in n: return "HOME", n
    if away_team and away_team in n: return "AWAY", n

if spec.type in ("NHL_MATCH_GOALS", "NHL_PERIOD_TOTAL"):
    if n.startswith("Over"):  return "OVER",  n
    if n.startswith("Under"): return "UNDER", n

if spec.type == "NHL_BTTS":
    return ("YES", "Yes") if n.lower().startswith("yes") else ("NO", "No")

if spec.type == "NHL_FIRST_GOAL_SCORER_TEAM":
    if n == "No goal": return "NO_GOAL", "No goal"
    if home_team and home_team in n: return "HOME", n
    if away_team and away_team in n: return "AWAY", n
```

### 7.3 Event ingest — live-events fallback
`/tournaments/get-scheduled-events?categoryId=4` returns empty on our current plan; the cron falls back to `/tournaments/get-live-events?sport=ice-hockey` automatically:

```python
LIVE_ONLY_FALLBACK = {4: "ice-hockey"}

def _fetch_events(self, sport):
    payload = self.client.get_scheduled_sport_events(sport.id)
    events = (payload or {}).get("events") or []
    if events or sport.id not in LIVE_ONLY_FALLBACK:
        return payload
    logger.info("Scheduled empty for sport=%s; live-events fallback", sport.id)
    return self.client.get_live_sport_events(LIVE_ONLY_FALLBACK[sport.id])
```

Same call count (1 per tick). If scheduled-events ever starts returning hockey events, the fallback silently stops triggering — no further action needed.

---

## 8. Query & Filtering

No new endpoints. One new query param.

### 8.1 `scope_subject` shortcut on the markets endpoint
```
GET /api/events/{event_id}/markets
    ?category=MONEYLINE,TOTAL,PROPS_GAME,PROPS_TEAM  (CSV)
    &scope=FULL_GAME,P1,P2,P3                         (period axis CSV)
    &scope_subject=game|team                          (subject axis sugar, NEW)
    &type=NHL_MATCH_GOALS                             (exact)
    &live=true|false
    &team_id=3671                                     (filter to team props for this team)
    &min_decimal=1.5&max_decimal=5.0
```

`scope_subject=team` → `category IN ('PROPS_TEAM')`.
`scope_subject=game` → `category IN ('MONEYLINE','SPREAD','TOTAL','PROPS_GAME')`.

### 8.2 Hockey worked example
```
GET /api/events?sport=ice_hockey
GET /api/events/15950232?include=markets
GET /api/events/15950232/markets?category=TOTAL,MONEYLINE&scope=FULL_GAME
GET /api/events/15950232/markets?scope_subject=game
```

---

## 9. Edge Cases

### 9.1 Overtime vs regulation moneylines
Two distinct markets coexist:
- `NHL_MATCH_WINNER_INC_OT` (`scope=FULL_GAME`) — 2-way. Settles on whoever wins including OT/SO. This is the **verified-live** default.
- `NHL_MATCH_WINNER_REG` (`scope=FULL_GAME`, `marketPeriod="Regulation"`) — 3-way including `DRAW`. Settles on score at end of 60 min.

### 9.2 Shootout
Separate `scope=SHOOTOUT` slot for any market explicitly covering only the shootout. Shootout "goals" don't count toward `NHL_MATCH_GOALS` (hockey stat convention).

### 9.3 Empty net
Empty-net goals contribute to standard totals. If SofaScore ships an explicit `NHL_EMPTY_NET_GOAL` yes/no market, it lands as `PROPS_GAME` — taxonomy row commented in §3. Book-side settlement voids the market if no empty net is pulled.

### 9.4 Multiple provider feeds collapsing onto one market row
Observed live: `(marketId=1, period="Match")` appears twice in a single payload with distinct fractional odds. Current ingest collapses both onto `evt-<id>-ml-ft` and accumulates all 4 `sourceId` selections under it.

**Impact:** list views see 4 selections (2 HOME, 2 AWAY) instead of 2.
**Mitigation:** UI picks best or first per type. Acceptable v1 behaviour.
**Proper fix (future):** include a provider-feed id in the deterministic `market_id` and fan out to separate rows.

### 9.5 Pushes and half-points
Puck lines ±1.5 never push; integer lines can. Totals usually in halves; integers push. Settlement logic (out of scope) reads `line % 1 == 0` to detect.

### 9.6 Suspended markets
`Market.suspended = True` when SofaScore flags it. The row is still upserted so the `market_id` stays stable. UI greys out; consumers still show the last prices.

### 9.7 Scheduled-events returning empty
Observed on the current RapidAPI plan for hockey. Handled by the live-events fallback (§7.3). No code change required if this starts working — fallback silently deactivates once scheduled returns non-empty.

### 9.8 Placeholder `provider_market_id`s
`NHL_MATCH_WINNER_REG` / `NHL_PUCK_LINE` / `NHL_PERIOD_*` / `NHL_BTTS` / `NHL_FIRST_GOAL_SCORER_TEAM` are commented with real IDs **TBD** when a wider hockey payload gets returned by SofaScore. Fix is a single edit in [taxonomy.py](../core/event/odds/taxonomy.py) — no DB migration.

---

## 10. Live probe findings (applied)

Ran during implementation against sport=4, event 15950232 (Edmonton vs Anaheim, NHL Playoffs, live).

| Assumption | Finding | Action taken |
|---|---|---|
| Hockey uses `marketPeriod="Full-time"` | **False.** Uses `"Match"`. | Added `"Match": "FULL_GAME"` to `SCOPE_MAP`; hockey rows in `SOFASCORE_MARKET_MAP` keyed on `"Match"`. |
| Hockey ML is 3-way | **False.** 2-way (`"1"` / `"2"`). | `classify_choice` for `NHL_MATCH_WINNER_INC_OT` returns only HOME/AWAY; `"X"` falls through. |
| `get-scheduled-events?categoryId=4` returns events | **False.** Returns `{"events": []}`. | Live-events fallback via `/tournaments/get-live-events?sport=ice-hockey`. |
| `get-all-odds` returns hockey markets | **True.** Market IDs 1 and 9 confirmed. | Taxonomy rows active and working. |
| Single provider feed per market | **False.** Two rows observed for same `(marketId, period)`. | Noted as edge case 9.4. |

**Pipeline result:** 5 live NHL events ingested, 1 odds probe returned 3 normalized markets end-to-end (moneyline + total 7.5). Hockey is production-ready for the markets we've validated.

---

**Implementation status: shipped.** Taxonomy + scopes + classifier + fallback all live. Remaining work is data-driven — probe an in-season, in-playoff NHL payload at a different phase of the game to pick up the commented-out `provider_market_id`s (spread, BTTS, first-team-to-score, period markets).
