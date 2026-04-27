# Unified Odds System — Architecture Plan

**Scope:** American Football (SofaScore sport id `63`), Basketball (`2`), Soccer (`1`).
**Source:** SofaScore via RapidAPI — structure validated against [/Users/joem/dev/sports-scores/json/match_odds__14024001.json](../../sports-scores/json/match_odds__14024001.json).
**Constraint:** 500 RapidAPI calls/month total.
**Market coverage:** Game-level and team-level markets only. **No player props.**
**API style:** REST only. No WebSockets — SofaScore is pull-only, so server-side push would just re-wrap polling. Flutter polls our cached REST endpoints instead.
**Builds on:** the completed Event/Team refactor ([refactor-plan.md](refactor-plan.md)). `Sport`, `Team`, and `Event` models already live on SofaScore IDs. `Bookmaker` / `Market` / `Outcome` are orphaned and will be replaced by the schema below.

---

## 1. Overview

### What we're building
A three-layer odds pipeline that normalizes SofaScore's per-match odds payload into a consistent internal schema across three sports, stays under the quota, and serves a Flutter client over REST.

```
┌─────────────────────────────────────────────────────────────┐
│  SofaScore raw JSON  (fractional odds, per-sport naming)    │
└──────────────────────┬──────────────────────────────────────┘
                       │  thin client + Redis counter
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Normalization pipeline                                     │
│    • marketId → MarketCategory + MarketScope                │
│    • fractional → decimal                                   │
│    • choice.name + choiceGroup → Selection (HOME/OVER/…)    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Django models: Event → Market → Selection → OddsQuote      │
│  (time-series OddsQuote for line-movement history)          │
└──────────────────────┬──────────────────────────────────────┘
                       │  Redis cache: list 60s, detail 10s
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  REST API  (client polls; SofaScore has no push feed, so    │
│  server-side WebSockets would only re-wrap polling)         │
└─────────────────────────────────────────────────────────────┘
```

### Non-goals (for this plan)
- **Player props** (`passing_yards`, `points`, `goal scorers`, etc.). Explicitly out of scope. SofaScore's public odds feed doesn't expose them anyway, and you want to ship focused.
- **Parlays.** Parlay support is **client-side composition** over single selections for v1. No server-side parlay leg reconciliation.
- **Bet settlement.** Separate concern.
- **GraphQL.** REST only.

### Budget math (unchanged from events refactor)
- `/tournaments/get-scheduled-events`: 3 sports × 2 ticks/day × 30 = **180 calls/month**
- `/matches/get-all-odds`: remaining **320 calls/month**
  - At a naive "refresh all upcoming events once a day" cadence: unsustainable (typical upcoming window = 50+ events).
  - **User-triggered + aggressive cache** — see §6.

### Assumptions
| Assumption | Rationale | What breaks if wrong |
|---|---|---|
| SofaScore `marketId` is stable per market type | Confirmed for soccer (1, 9, 17 are canonical). Basketball/AF TBD. | Taxonomy mapping table (§7) — one data edit. |
| Fractional is always parseable as `a/b` | All samples conform. | Add "evens" and decimal parser fallback. |
| Basketball/AF odds follow the same envelope | `get-all-odds` has a uniform shape across sports. | Per-sport normalizer, not a blocker. |

---

## 2. Universal Market Categories

Every market in the system decomposes into three orthogonal dimensions:

| Dimension | Values | Purpose |
|---|---|---|
| `category` | `MONEYLINE`, `SPREAD`, `TOTAL`, `PROPS_GAME`, `PROPS_TEAM` | *What kind of bet* |
| `scope` | `FULL_GAME`, `H1`, `H2`, `Q1`, `Q2`, `Q3`, `Q4`, `OVERTIME`, `PERIOD_N` | *What segment* |
| `line` *(SPREAD/TOTAL/some props)* | signed decimal, nullable otherwise | *The number* |

Five categories total — `PROPS_PLAYER` is explicitly **not** in the enum.

### 2.1 MONEYLINE (match winner)
**Meaning:** Pick the winning side (+ draw for soccer).
**Sports:** AF, BB (2-way); Soccer (3-way).
**Scope variants:** `FULL_GAME`, `H1`, `Q1..Q4` (BB/AF), `H1`/`H2` (Soccer).
**Selections:** `HOME`, `AWAY`, `DRAW` (nullable — only soccer uses it).

**Normalized JSON shape:**
```json
{
  "category": "MONEYLINE",
  "scope": "FULL_GAME",
  "line": null,
  "selections": [
    { "type": "HOME", "label": "Brighton & Hove Albion",
      "odds": { "decimal": 2.30, "american": 130, "fractional": "13/10" },
      "movement": "down", "suspended": false },
    { "type": "DRAW", "label": "Draw",
      "odds": { "decimal": 3.60, "american": 260, "fractional": "13/5" },
      "movement": "flat", "suspended": false },
    { "type": "AWAY", "label": "Chelsea",
      "odds": { "decimal": 2.90, "american": 190, "fractional": "19/10" },
      "movement": "up", "suspended": false }
  ]
}
```

### 2.2 SPREAD / HANDICAP
**Meaning:** One side is given a line; bet pays if result adjusted by the line is in your favour.
**Sports:** AF (spread), BB (spread), Soccer (Asian handicap — line can be `.25` or `.75`).
**Scope variants:** `FULL_GAME`, `H1`, `Q1..Q4` (sport-dependent).
**Selections:** `HOME`, `AWAY` (each with signed line stored on the Market row; the sides carry opposite signs implicitly).

```json
{
  "category": "SPREAD",
  "scope": "FULL_GAME",
  "line": -3.5,
  "selections": [
    { "type": "HOME", "label": "Chiefs -3.5",
      "odds": { "decimal": 1.91, "american": -110, "fractional": "10/11" } },
    { "type": "AWAY", "label": "Broncos +3.5",
      "odds": { "decimal": 1.91, "american": -110, "fractional": "10/11" } }
  ]
}
```

Soccer Asian handicaps in SofaScore arrive as `"(-0.25) Brighton & Hove Albion"` in the choice `name`. The normalizer extracts the sign, magnitude, and side.

### 2.3 TOTAL (Over/Under)
**Meaning:** Will the combined score/stat be over or under a line.
**Sports:** all three, many lines per event (SofaScore ships 0.5, 1.5, 2.5, … for soccer goals).
**Scope variants:** `FULL_GAME`, `H1`, `Q1..Q4`, `OVERTIME`.

```json
{
  "category": "TOTAL",
  "scope": "FULL_GAME",
  "line": 2.5,
  "selections": [
    { "type": "OVER",  "label": "Over 2.5",
      "odds": { "decimal": 1.91, "american": -110, "fractional": "10/11" } },
    { "type": "UNDER", "label": "Under 2.5",
      "odds": { "decimal": 1.91, "american": -110, "fractional": "10/11" } }
  ]
}
```

Each `choiceGroup` in SofaScore becomes a separate `Market` row with a distinct `line` value. This is intentional: a UI picker for "Which line?" reads directly from the DB rows.

### 2.4 PROPS_GAME (match-level specials)
**Meaning:** Event-level yes/no or multi-way markets that aren't a winner, spread, or total.
**Sports:**
- **Soccer:** BTTS, Double chance, Draw no bet, First team to score, Total cards, Total corners.
- **BB / AF:** fewer of these in practice, but the category exists for things like "will the game go to overtime?".

### 2.5 PROPS_TEAM (team-level stats, not player)
**Meaning:** One side's stat line — e.g. "Home team total points over 24.5".
**Sports:** all three.
**Structure:** `side = "HOME"|"AWAY"` on the Market row; selections are `OVER`/`UNDER`.

```json
{
  "category": "PROPS_TEAM",
  "type": "SOCCER_TEAM_TOTAL_GOALS",
  "scope": "FULL_GAME",
  "side": "HOME",
  "line": 1.5,
  "selections": [
    { "type": "OVER",  "label": "Brighton Over 1.5",  "odds": { "decimal": 1.85, "american": -118, "fractional": "17/20" } },
    { "type": "UNDER", "label": "Brighton Under 1.5", "odds": { "decimal": 2.00, "american": 100,  "fractional": "1/1"   } }
  ]
}
```

### 2.6 PERIOD-BASED MARKETS
Not a category on its own — it's the `scope` axis on top of the four above. Any `MONEYLINE`/`SPREAD`/`TOTAL`/`PROPS_TEAM` can be period-scoped. SofaScore's `marketPeriod` field (`Full-time`, `1st half`, `2nd half`, etc.) maps directly.

### 2.7 LIVE / IN-PLAY
Not a category — it's a flag. `Market.is_live = payload.markets[*].isLive`. Live markets get much shorter cache TTLs (see §6).

### 2.8 PARLAYS / COMBINATIONS
**Client-side composition for v1.** Flutter builds a slip of `Selection` IDs, posts to `POST /api/slips` which:
- re-fetches each selection's current odds (from cache),
- multiplies decimals,
- records the slip.
No new provider call. Legs share no DB row — they're just FK rows on a `SlipLeg` table (out of scope for this plan's data model).

### 2.9 Odds format — always three representations
Store **decimal** as the source of truth (float, 2 dp precision is enough for display but keep 4 dp in DB for downstream math). Compute American and fractional on the fly via a tiny helper:

```python
def decimal_to_american(d: float) -> int:
    if d >= 2.0:
        return int(round((d - 1) * 100))
    return int(round(-100 / (d - 1)))

def fractional_to_decimal(s: str) -> float:
    num, den = s.split("/")
    return float(num) / float(den) + 1.0
```

API responses carry all three formats (`odds.decimal`, `odds.american`, `odds.fractional`). Flutter picks.

---

## 3. Sport-Specific Market Extensions

All per-sport markets below fit one of the five universal categories. Player-prop markets are **not** included — the schema simply doesn't have them.

### 3.1 American Football (sport_id = 63)
**Universal coverage:** MONEYLINE (2-way), SPREAD, TOTAL — with `Q1..Q4` and `H1`/`H2` scopes.

**PROPS_TEAM**
- `AF_TEAM_TOTAL_POINTS` — `OVER` / `UNDER` per side; line in points.

**PROPS_GAME**
- Anything period-scoped already covered by universal categories (1st-quarter winner, 1st-half total, etc.).

### 3.2 Basketball (sport_id = 2)
**Universal coverage:** MONEYLINE (2-way, no draw), SPREAD, TOTAL — with `Q1..Q4`, `H1`/`H2`, `OVERTIME`.

**PROPS_TEAM**
- `BB_TEAM_TOTAL_POINTS` — `OVER` / `UNDER` per side; line in points.

**PROPS_GAME**
- Period-scoped variants (e.g. "highest-scoring quarter") if SofaScore exposes them. Fill in as we inspect real payloads.

### 3.3 Soccer (sport_id = 1)
**Universal coverage:** MONEYLINE (3-way), Asian handicap (SPREAD), TOTAL goals (lines 0.5 through 7.5).

**PROPS_GAME**
- `SOCCER_BTTS` — `YES` / `NO`  *(SofaScore marketId=5)*
- `SOCCER_DOUBLE_CHANCE` — `1X`, `X2`, `12`  *(SofaScore marketId=2)*
- `SOCCER_DRAW_NO_BET` — `HOME`, `AWAY`  *(marketId=4)*
- `SOCCER_FIRST_TEAM_TO_SCORE` — `HOME`, `AWAY`, `NO_GOAL`  *(marketId=6)*
- `SOCCER_CORNERS_TOTAL` — `OVER` / `UNDER`  *(marketId=21)*
- `SOCCER_CARDS_TOTAL` — `OVER` / `UNDER`  *(marketId=20)*

**PROPS_TEAM**
- `SOCCER_TEAM_TOTAL_GOALS` — `OVER` / `UNDER` per side.

### Inheritance diagram
```
MarketCategory (enum, shared across sports)
├── MONEYLINE   ◄── every sport's match winner
├── SPREAD      ◄── AF/BB point spread; Soccer Asian handicap
├── TOTAL       ◄── goals/points/etc. over-under
├── PROPS_GAME  ◄── BTTS, DNB, corners, double-chance, first-scorer (soccer); special game markets (BB/AF)
└── PROPS_TEAM  ◄── team totals across all sports
```

The DB stores `category` + a `type` string (e.g. `SOCCER_BTTS`) — `category` is what you filter on; `type` is what the UI renders. No per-sport table; one `Market` row shape for everything.

---

## 4. JSON Refactor (Before → After)

### 4.1 BEFORE — raw SofaScore (abridged from [match_odds__14024001.json](../../sports-scores/json/match_odds__14024001.json))

```json
{
  "markets": [
    {
      "sourceId": 192501039,
      "structureType": 1,
      "marketId": 1,
      "marketName": "Full time",
      "marketGroup": "1X2",
      "marketPeriod": "Full-time",
      "isLive": false,
      "suspended": false,
      "id": 303794550,
      "choices": [
        { "name": "1", "fractionalValue": "13/10", "initialFractionalValue": "69/50", "change": -1, "winning": true,  "sourceId": 998112593 },
        { "name": "X", "fractionalValue": "13/5",  "initialFractionalValue": "13/5",  "change":  0, "winning": false, "sourceId": 998112596 },
        { "name": "2", "fractionalValue": "19/10", "initialFractionalValue": "17/10", "change":  1, "winning": false, "sourceId": 998112597 }
      ]
    },
    {
      "marketId": 9,
      "marketName": "Match goals",
      "marketGroup": "Match goals",
      "marketPeriod": "Full-time",
      "choiceGroup": "2.5",
      "structureType": 2,
      "isLive": false,
      "choices": [
        { "name": "Over",  "fractionalValue": "10/11", "change": -1 },
        { "name": "Under", "fractionalValue": "10/11", "change":  1 }
      ]
    }
  ],
  "eventId": 14024001
}
```

**Problems with the raw shape:**
1. Naming is sport-dependent (`"1"/"X"/"2"` vs `"Over"/"Under"` vs `"(-0.25) Brighton & Hove Albion"`).
2. Line value hidden in `choiceGroup` (a string).
3. Odds only as fractional strings — no decimal or American.
4. `marketGroup` is free-text, not a typed taxonomy.
5. Each O/U line is a separate market, but they share the same `marketId=9` (grouping is by `(marketId, choiceGroup)`).
6. No stable "this is the home side" flag — derived positionally.

### 4.2 AFTER — unified JSON (what we serve to Flutter)

One event, two markets, shown with both a moneyline (3-way) and a totals line:

```json
{
  "event_id": 14024001,
  "sport": "soccer",
  "league": { "id": 17, "name": "Premier League", "slug": "premier-league" },
  "home_team": { "id": 30, "name": "Brighton & Hove Albion", "short": "Brighton" },
  "away_team": { "id": 38, "name": "Chelsea", "short": "Chelsea" },
  "start_time": "2025-04-26T15:00:00Z",
  "is_live": false,
  "markets": [
    {
      "market_id": "evt-14024001-ml-ft",
      "category": "MONEYLINE",
      "type": "SOCCER_MATCH_WINNER",
      "scope": "FULL_GAME",
      "line": null,
      "side": "",
      "suspended": false,
      "last_updated": "2025-04-26T14:37:12Z",
      "selections": [
        { "selection_id": 998112593, "type": "HOME", "label": "Brighton",
          "odds": { "decimal": 2.30, "american": 130, "fractional": "13/10" },
          "movement": "down", "suspended": false },
        { "selection_id": 998112596, "type": "DRAW", "label": "Draw",
          "odds": { "decimal": 3.60, "american": 260, "fractional": "13/5" },
          "movement": "flat", "suspended": false },
        { "selection_id": 998112597, "type": "AWAY", "label": "Chelsea",
          "odds": { "decimal": 2.90, "american": 190, "fractional": "19/10" },
          "movement": "up", "suspended": false }
      ]
    },
    {
      "market_id": "evt-14024001-tot-ft-2.5",
      "category": "TOTAL",
      "type": "SOCCER_MATCH_GOALS",
      "scope": "FULL_GAME",
      "line": 2.5,
      "side": "",
      "suspended": false,
      "last_updated": "2025-04-26T14:37:12Z",
      "selections": [
        { "selection_id": 998112599, "type": "OVER",  "label": "Over 2.5",
          "odds": { "decimal": 1.91, "american": -110, "fractional": "10/11" },
          "movement": "down" },
        { "selection_id": 998112602, "type": "UNDER", "label": "Under 2.5",
          "odds": { "decimal": 1.91, "american": -110, "fractional": "10/11" },
          "movement": "up" }
      ]
    }
  ]
}
```

**Key normalization wins:**
- Every selection has a `type` enum (`HOME`, `AWAY`, `DRAW`, `OVER`, `UNDER`, `YES`, `NO`, …) so Flutter never parses "1"/"X"/"2" again.
- `line` is a typed float, not a string.
- Odds are pre-converted to all three formats.
- `market_id` is a deterministic string so Flutter can cache and diff cheaply; `selection_id` is SofaScore's `sourceId` (stable across refresh).

---

## 5. Data Model

### 5.1 Relational model (Django)

Lives in `core/event/models/odds/` (new subpackage) to keep it separated from the existing `Event` / `Team` / `Sport` chain.

```python
# core/event/models/odds/market.py
class MarketCategory(models.TextChoices):
    MONEYLINE   = "MONEYLINE"
    SPREAD      = "SPREAD"
    TOTAL       = "TOTAL"
    PROPS_GAME  = "PROPS_GAME"
    PROPS_TEAM  = "PROPS_TEAM"

class MarketScope(models.TextChoices):
    FULL_GAME  = "FULL_GAME"
    H1         = "H1"
    H2         = "H2"
    Q1         = "Q1"
    Q2         = "Q2"
    Q3         = "Q3"
    Q4         = "Q4"
    OVERTIME   = "OVERTIME"
    PERIOD_N   = "PERIOD_N"  # for sports with variable periods

class SelectionType(models.TextChoices):
    HOME   = "HOME"
    AWAY   = "AWAY"
    DRAW   = "DRAW"
    OVER   = "OVER"
    UNDER  = "UNDER"
    YES    = "YES"
    NO     = "NO"
    # soccer double-chance
    X1     = "1X"
    X2     = "X2"
    HOME_OR_AWAY = "12"
    NO_GOAL = "NO_GOAL"
    # fallback for unknown — never queried, only displayed
    CUSTOM = "CUSTOM"


class Market(models.Model):
    id = models.CharField(max_length=64, primary_key=True)   # deterministic: evt-{event_id}-{kind}-{scope}[-{line}][-{side}]
    event = models.ForeignKey("core_event.Event", on_delete=models.CASCADE, related_name="markets")
    sport = models.ForeignKey("core_event.Sport", on_delete=models.PROTECT)  # denorm for index only

    category = models.CharField(max_length=16, choices=MarketCategory.choices, db_index=True)
    type     = models.CharField(max_length=48, db_index=True)   # e.g. SOCCER_BTTS, BB_TEAM_TOTAL_POINTS
    scope    = models.CharField(max_length=16, choices=MarketScope.choices, default=MarketScope.FULL_GAME)
    line     = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    side     = models.CharField(max_length=8, blank=True)  # team-totals: "HOME" / "AWAY" / ""

    # Links to the SofaScore market — one row per (marketId, choiceGroup)
    provider = models.CharField(max_length=32, default="sofascore")
    provider_market_id    = models.BigIntegerField(db_index=True)
    provider_choice_group = models.CharField(max_length=16, blank=True)

    # For team props — points to the side the prop is about
    subject_team = models.ForeignKey("core_event.Team", null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")

    is_live   = models.BooleanField(default=False)
    suspended = models.BooleanField(default=False)
    last_updated = models.DateTimeField(db_index=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_market"
        indexes = [
            models.Index(fields=["event", "category", "scope"]),
            models.Index(fields=["sport", "category", "is_live"]),
            models.Index(fields=["event", "type"]),
        ]


# core/event/models/odds/selection.py
class Selection(models.Model):
    id = models.BigIntegerField(primary_key=True)   # SofaScore `choices[*].sourceId` — stable
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name="selections")
    type   = models.CharField(max_length=16, choices=SelectionType.choices)
    label  = models.CharField(max_length=128)       # display text, raw-ish
    suspended = models.BooleanField(default=False)

    # Latest quote (denormalized from OddsQuote for fast list reads)
    decimal_odds         = models.DecimalField(max_digits=8, decimal_places=4)
    opening_decimal_odds = models.DecimalField(max_digits=8, decimal_places=4)
    movement = models.SmallIntegerField(default=0)   # -1, 0, +1

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_selection"
        indexes = [models.Index(fields=["market", "type"])]


# core/event/models/odds/quote.py
class OddsQuote(models.Model):
    """Append-only: one row per (selection, refresh). Used for line-movement charts.
    A `Market` refresh writes N new rows — one per selection. We keep N * latest_refreshes;
    older rows age out via a daily compaction task."""
    id = models.BigAutoField(primary_key=True)
    selection    = models.ForeignKey(Selection, on_delete=models.CASCADE, related_name="quotes")
    decimal_odds = models.DecimalField(max_digits=8, decimal_places=4)
    captured_at  = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "core_odds_quote"
        indexes = [models.Index(fields=["selection", "captured_at"])]
        constraints = [
            models.UniqueConstraint(fields=["selection", "captured_at"], name="uq_quote_selection_captured")
        ]
```

**What becomes of old models:**
- `Bookmaker`, `Market` (old), `Outcome` → **drop**. One destructive migration; dev DB wipe already in motion.
- `Bet` (in `core.game`) references old `Market`/`Outcome` — repoint FKs to the new `Market` and `Selection`. No prod data to migrate, just reset.

### 5.2 Deterministic market_id

```
evt-{event_id}-{kind}[-{scope}][-{line}][-{side}]
  kind  = ml | spread | total | dc | dnb | btts | corners | cards | teamtot | …
  scope = ft | h1 | h2 | q1 | q2 | q3 | q4 | ot
  line  = "2_5"  (dot replaced by underscore)
  side  = home | away  (only for team-total props)
```

Examples:
- `evt-14024001-ml-ft` → moneyline, full-time
- `evt-14024001-total-ft-2_5` → total goals 2.5 full-time
- `evt-14024001-spread-q1-3_5-home` → Q1 home team -3.5
- `evt-14024001-teamtot-ft-1_5-home` → home team total goals 1.5 full-time

Deterministic IDs mean Flutter can diff market lists across refreshes without server-side ID mapping tables, and the upsert in normalization stays idempotent.

### 5.3 JSON schema (strict, for API responses)

```jsonc
{
  "event_id": 14024001,                    // bigint, SofaScore id
  "sport":    "soccer",                    // enum: soccer|basketball|american_football
  "league":   { "id": 17, "name": "string", "slug": "string" },
  "home_team":{ "id": 30, "name": "string", "short": "string" },
  "away_team":{ "id": 38, "name": "string", "short": "string" },
  "start_time":"ISO-8601",
  "status":   "notstarted|inprogress|finished|postponed",
  "is_live":  false,
  "markets": [{
    "market_id":    "evt-…",               // deterministic string
    "category":     "MONEYLINE|SPREAD|TOTAL|PROPS_GAME|PROPS_TEAM",
    "type":         "SPORT_MARKET_TYPE",   // e.g. SOCCER_BTTS, BB_TEAM_TOTAL_POINTS
    "scope":        "FULL_GAME|H1|H2|Q1…Q4|OVERTIME|PERIOD_N",
    "line":         2.5,                   // nullable decimal
    "side":         "HOME|AWAY|",          // team-prop only
    "subject": null | { "kind":"team", "id":30, "name":"Brighton" },
    "suspended":    false,
    "last_updated": "ISO-8601",
    "selections": [{
      "selection_id": 998112599,           // bigint, stable
      "type":         "HOME|AWAY|DRAW|OVER|UNDER|YES|NO|1X|X2|12|NO_GOAL|CUSTOM",
      "label":        "string",
      "odds": { "decimal": 1.91, "american": -110, "fractional": "10/11" },
      "movement":     "up|down|flat",
      "suspended":    false
    }]
  }]
}
```

---

## 6. API Refactor Strategy

### 6.1 Request flow + call cost

```
/sports/list                        ─┐  1 call / one-shot seed (manual)
                                     │
/tournaments/get-scheduled-events    ─┤  3 sports × 2 ticks/day × 30 = 180 calls/month
  → upserts Events + Teams + denorm.  │
    league fields on the Event row    │
                                     │
/matches/get-all-odds                ─┘  ≤ 320 calls/month budget
  → upserts Markets + Selections
```

### 6.2 Odds-call policy (the hard part)

The only way to hold 500/month is to **never poll odds blindly**. Three rules:

1. **Trigger on demand.** Odds for event `X` are fetched when:
   - a client hits `/api/events/{X}?include=markets`, **and**
   - the cached odds for `X` are older than the freshness threshold.
2. **Freshness thresholds** (per-event TTL, configurable):
   - Pre-match, not within 24h: **6 hours**.
   - Pre-match, within 24h: **30 minutes**.
   - Live: **30 seconds**.
3. **Hard floor.** Each event gets a per-month call counter (Redis hash `sofascore:odds:{event_id}:{YYYY-MM}`). Cap per event = 10 refreshes/month (reasonable for a pre-match + a few live dips). Refuses refresh past the floor → returns stale cache with a `stale: true` flag in the response.

### 6.3 Cache topology (Redis)

| Key | Value | TTL |
|---|---|---|
| `sofascore:sports:list` | raw JSON from `/sports/list` | 30 days |
| `sofascore:events:{sport_id}` | raw JSON from scheduled-events | **12h** (match cron cadence) |
| `sofascore:odds:{event_id}` | raw JSON from `/matches/get-all-odds` | **dynamic** (see §6.2) |
| `api:events:{sport}:{date}:{etag}` | serialized REST response | 60s |
| `api:event:{id}` | serialized single-event response | 10s (pre-match) / 3s (live) |
| `sofascore:calls:{YYYY-MM}` | monthly call counter (global) | 40 days |
| `sofascore:odds:{event_id}:{YYYY-MM}` | per-event call counter | 40 days |

The raw-JSON cache (first three rows) exists so that a client hitting the API 5× in 10 seconds doesn't each trigger a SofaScore call — only the first passes through, the rest read cache.

### 6.4 Incremental updates

On every `/matches/get-all-odds` hit the normalizer upserts by deterministic `market_id` + `selection_id`. A new `OddsQuote` row is inserted only when `decimal_odds != Selection.decimal_odds` (movement detection). That keeps the time-series table from ballooning and gives us cheap "has odds changed?" signal.

### 6.5 What batching is possible
Almost none — SofaScore has no bulk odds endpoint. The only real batching is:
- Use **scheduled-events** payload (already batched per sport) to prime the Event+Team tables.
- Group REST requests from the Flutter client (`?include=markets` rather than a second round-trip).
- WebSocket fan-out: one odds refresh → N client pushes.

---

## 7. Normalization Layer

File: `core/event/odds/normalize.py`. One function per category; one dispatcher.

### 7.1 Taxonomy map (the only source of truth)

```python
# core/event/odds/taxonomy.py
from dataclasses import dataclass

@dataclass(frozen=True)
class MarketSpec:
    category: str     # MarketCategory value
    type: str         # e.g. "SOCCER_BTTS"
    kind_slug: str    # short slug used in the deterministic market_id

# (sport_id, provider_market_id, market_period) -> MarketSpec
# Expand as more markets are encountered.
SOFASCORE_MARKET_MAP: dict[tuple, MarketSpec] = {
    # Soccer (1)
    (1, 1, "Full-time"): MarketSpec("MONEYLINE", "SOCCER_MATCH_WINNER",   "ml"),
    (1, 1, "1st half"):  MarketSpec("MONEYLINE", "SOCCER_MATCH_WINNER",   "ml"),
    (1, 2, "Full-time"): MarketSpec("PROPS_GAME", "SOCCER_DOUBLE_CHANCE", "dc"),
    (1, 4, "Full-time"): MarketSpec("PROPS_GAME", "SOCCER_DRAW_NO_BET",   "dnb"),
    (1, 5, "Full-time"): MarketSpec("PROPS_GAME", "SOCCER_BTTS",          "btts"),
    (1, 6, "Full-time"): MarketSpec("PROPS_GAME", "SOCCER_FIRST_SCORER",  "first"),
    (1, 9, "Full-time"): MarketSpec("TOTAL",      "SOCCER_MATCH_GOALS",   "total"),
    (1, 17,"Full-time"): MarketSpec("SPREAD",     "SOCCER_ASIAN_HANDICAP","spread"),
    (1, 20,"Full-time"): MarketSpec("PROPS_GAME", "SOCCER_CARDS_TOTAL",   "cards"),
    (1, 21,"Full-time"): MarketSpec("PROPS_GAME", "SOCCER_CORNERS_TOTAL", "corners"),

    # Basketball (2) — to populate once we inspect real payloads
    # (2, ??, "Full-time"): MarketSpec("MONEYLINE", "BB_MATCH_WINNER",      "ml"),
    # (2, ??, "Full-time"): MarketSpec("SPREAD",    "BB_POINT_SPREAD",      "spread"),
    # (2, ??, "Full-time"): MarketSpec("TOTAL",     "BB_MATCH_POINTS",      "total"),
    # (2, ??, "Full-time"): MarketSpec("PROPS_TEAM","BB_TEAM_TOTAL_POINTS", "teamtot"),

    # American football (63) — ditto
}

SCOPE_MAP = {
    "Full-time":   "FULL_GAME",
    "1st half":    "H1",
    "2nd half":    "H2",
    "1st quarter": "Q1",
    "2nd quarter": "Q2",
    "3rd quarter": "Q3",
    "4th quarter": "Q4",
    "Overtime":    "OVERTIME",
}
```

We'll inspect a live basketball + AF payload before filling those `??` rows — that's a one-time investigation. The design doesn't depend on knowing them *right now*.

### 7.2 Selection normalizer

```python
def classify_choice(spec: MarketSpec, raw_name: str, *, home_team: str, away_team: str) -> tuple[str, str]:
    """Return (selection_type, clean_label)."""
    n = raw_name.strip()

    if spec.category == "MONEYLINE" and spec.type == "SOCCER_MATCH_WINNER":
        return {"1": ("HOME", home_team), "X": ("DRAW", "Draw"), "2": ("AWAY", away_team)}[n]

    if spec.category == "TOTAL":
        if n.startswith("Over"):   return "OVER", n
        if n.startswith("Under"):  return "UNDER", n

    if spec.type == "SOCCER_BTTS":
        return ("YES", "Yes") if n == "Yes" else ("NO", "No")

    if spec.type == "SOCCER_DOUBLE_CHANCE":
        return {"1X": "1X", "X2": "X2", "12": "12"}[n], n

    if spec.type == "SOCCER_ASIAN_HANDICAP":
        # name looks like "(-0.25) Brighton & Hove Albion"
        if home_team in n:  return "HOME", n
        if away_team in n:  return "AWAY", n

    if spec.type == "SOCCER_FIRST_SCORER":
        if n == "No goal": return "NO_GOAL", "No goal"
        if home_team in n: return "HOME", n
        if away_team in n: return "AWAY", n

    return "CUSTOM", n
```

Missing rules return `CUSTOM` — they still render correctly, they just don't participate in typed filtering until we add them to the map.

### 7.3 Full ingest function

```python
def ingest_odds(event: Event, payload: dict) -> None:
    home_name = event.home_team.name
    away_name = event.away_team.name
    now = timezone.now()

    for raw_market in payload.get("markets", []):
        period = raw_market.get("marketPeriod") or "Full-time"
        spec = SOFASCORE_MARKET_MAP.get((event.sport_id, raw_market["marketId"], period))
        if spec is None:
            # unknown market type — skip for now; log once
            continue

        scope = SCOPE_MAP.get(period, "FULL_GAME")
        line_str = raw_market.get("choiceGroup")
        line = float(line_str) if line_str else None

        market_id = build_market_id(event.id, spec.kind_slug, scope, line, side=None)
        market, _ = Market.objects.update_or_create(
            id=market_id,
            defaults=dict(
                event=event,
                sport_id=event.sport_id,
                category=spec.category,
                type=spec.type,
                scope=scope,
                line=line,
                provider="sofascore",
                provider_market_id=raw_market["marketId"],
                provider_choice_group=line_str or "",
                is_live=bool(raw_market.get("isLive")),
                suspended=bool(raw_market.get("suspended")),
                last_updated=now,
            ),
        )

        for raw_choice in raw_market.get("choices", []):
            sel_type, label = classify_choice(
                spec, raw_choice["name"], home_team=home_name, away_team=away_name
            )
            decimal_odds = fractional_to_decimal(raw_choice["fractionalValue"])
            opening      = fractional_to_decimal(raw_choice.get("initialFractionalValue", raw_choice["fractionalValue"]))
            movement     = raw_choice.get("change", 0)

            sel, created = Selection.objects.update_or_create(
                id=raw_choice["sourceId"],
                defaults=dict(
                    market=market,
                    type=sel_type,
                    label=label,
                    decimal_odds=decimal_odds,
                    opening_decimal_odds=opening,
                    movement=movement,
                    suspended=bool(raw_choice.get("suspended", False)),
                ),
            )

            # Time-series row only if the price actually moved
            if created or sel.decimal_odds != decimal_odds:
                OddsQuote.objects.create(
                    selection=sel, decimal_odds=decimal_odds, captured_at=now
                )
```

This is ~60 lines of hot-path code; the taxonomy table is ~30 rows of data. That's the entire normalization layer.

---

## 8. Query & Filtering Design

**REST only.** Endpoints below. (No GraphQL.)

### 8.1 Endpoints

```
GET /api/events
    ?sport=soccer|basketball|american_football   (required, single)
    &date=YYYY-MM-DD                              (default: today + 3 days window)
    &league=17                                    (optional)
    &live=true|false                              (optional)
    &include=markets                              (optional — inlines top 3 markets)
    &page=1&page_size=50

→ 200: { "count": N, "next": url|null, "results": [<event json>, …] }

GET /api/events/{event_id}
    ?include=markets                              (inlines all markets)

→ 200: <single event json>

GET /api/events/{event_id}/markets
    ?category=MONEYLINE,TOTAL,PROPS_GAME,PROPS_TEAM  (CSV filter)
    &scope=FULL_GAME,H1                              (CSV filter)
    &type=SOCCER_BTTS                                (exact match)
    &live=true|false
    &min_decimal=1.5&max_decimal=5.0                 (prices within range)
    &team_id=30                                      (filter to team-subject props)

→ 200: { "markets": [<market json>, …] }

GET /api/selections/{selection_id}/movement
    ?since=ISO-8601                               (default: last 24h)

→ 200: { "quotes": [{ "decimal": 1.91, "captured_at": "…" }, …] }

POST /api/slips                                   (parlay composition — client-side legs)
    Body: { "legs": [{ "selection_id": 998112599 }, …] }

→ 201: { "slip_id": "…", "legs": […with current odds snapshot…], "combined_decimal": 6.84 }
```

### 8.2 Filter implementation notes

- All list endpoints are paginated (existing pagination class, bumped page size to 50).
- Odds-threshold filtering (`min_decimal` / `max_decimal`) uses a DB index on `Selection.decimal_odds` + a join; cost is fine up to ~20k selections per sport.
- `?include=markets` on the list endpoint inlines **only the top-3 markets** per event (Moneyline / Spread / primary Total at median line). Prevents N+1 requests on list views in Flutter. Full market catalog stays on the detail endpoint.
- Teams in filter args are by SofaScore id (already our PKs).
- `category=PROPS_GAME,PROPS_TEAM` is the obvious "show me the specials tab" call.

---

## 9. Scalability Strategy

### 9.1 Live updates — REST polling, not WebSockets

SofaScore has no push/WebSocket feed. Any server-side WebSocket layer would
still have to poll `/matches/get-all-odds` on a timer and then fan out to
sockets — adding infra (Django Channels, a second process tier) without
solving the underlying freshness problem. Skip it for v1.

**Pattern — Flutter polls our REST endpoints, we poll SofaScore sparingly:**

```
Client  ────►  GET /api/events?sport=…            (poll every 60s on list screens)
Client  ────►  GET /api/events/{id}?include=markets (poll every 10–30s on detail)
                                                  │
                                                  ▼
Server  reads Redis cache → if fresh, return it
        else → fetch SofaScore once (respecting per-event cap), normalize, cache, return
```

Cache TTLs (see §6) make this cheap: a hot detail screen with 20 simultaneous
viewers triggers at most one SofaScore call per freshness window.

**When Flutter needs near-live scoring:** lean on the existing freshness
tiers (30s TTL for `status_type="inprogress"`). That gives a ~30s ceiling on
staleness for a live match without any WebSocket infra. Good enough for v1.

### 9.2 Redis strategy (expanded from §6)

- **Persistent data** (counters, monthly quotas): Redis with AOF on, separate DB index from cache.
- **Cache**: Redis LRU, DB index 1 (the one already wired into `django_redis`).

One Redis instance per env is fine for now; split DBs keep the namespaces clean without operational overhead.

### 9.3 Database indexing (critical)

The two high-frequency queries:

1. **Event list for sport + date window:**
   ```sql
   SELECT … FROM core_event_event
   WHERE sport_id = 1 AND start_time BETWEEN X AND Y AND status_type IN ('notstarted','inprogress')
   ORDER BY start_time;
   ```
   Needs: `(sport_id, status_type, start_time)` composite index. Already have `start_time` indexed; add the composite.

2. **Markets for an event, filtered by category/scope:**
   ```sql
   SELECT … FROM core_market
   WHERE event_id = ? AND category IN (…) AND scope IN (…);
   ```
   Needs: `(event_id, category, scope)` — covered in the model above.

3. **Time-series movement for one selection:**
   ```sql
   SELECT decimal_odds, captured_at FROM core_odds_quote
   WHERE selection_id = ? AND captured_at > ?;
   ```
   Needs: `(selection_id, captured_at)` — covered.

### 9.4 `OddsQuote` growth control

Append-only is fine until it isn't. Worst case:
- 3 sports × 30 events/sport/week active = 90 events
- 15 markets / event × 3 selections / market = 45 selections / event
- 10 refreshes / event ⇒ 10 × 45 = 450 quotes / event = 40K quotes / week, ~2M / year

Manageable, but not free. **Compaction cron:**
- For events > 7 days old: keep hourly samples + open + close.
- For events > 30 days old: keep open + close only.
- Runs weekly, batched in chunks of 10K rows.

### 9.5 Horizontal scaling

- **Web tier (Gunicorn):** stateless, scale horizontally. Existing setup.
- **Celery workers:** scale horizontally. On macOS local dev only, run `--pool=solo` (already set in [.vscode/launch.json](../.vscode/launch.json)). Prod stays prefork.
- **DB (Postgres):** single primary until we hit clear read contention. Read replica only after replication lag is the real bottleneck. Partitioning `OddsQuote` by month is a low-cost future move but don't pay for it pre-emptively.
- **Cache (Redis):** single instance → Redis Cluster or managed (Elasticache / Heroku Redis) once we outgrow a single node. For v1 unlikely.

### 9.6 Cost-efficiency ceiling

This whole plan is shaped around the 500-call RapidAPI ceiling. When we upgrade the RapidAPI plan (or add a second provider), the architecture absorbs it cleanly:

- Second provider → new `provider` value on `Market`; normalizer gets a second module; taxonomy table gets a second key namespace.
- Bigger quota → just raise the per-event refresh cap and the global `SOFT_LIMIT`. No schema change.
- **Adding player props later** → reintroduces `PROPS_PLAYER` as a sixth category and a `subject_player_id` field on `Market`. No restructure; purely additive.

That's the whole plan. Sign off on this doc, I'll implement it (models → migrations → normalizer → endpoints → channels) and gate each phase on smoke-test hits against real SofaScore basketball + AF payloads.
