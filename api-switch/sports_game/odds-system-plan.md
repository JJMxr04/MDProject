# Odds System — SportsGameOdds Edition

**Goal:** keep the unified 5-category market schema we already have ([sofa odds-system-plan.md](../sofa/odds-system-plan.md)), but feed it from SportsGameOdds's structured `oddID` taxonomy instead of SofaScore's free-text choice names. Most of the normalization layer **gets simpler, not more complex** — SGO already gives us typed components.

**Builds on:** [refactor-plan.md](refactor-plan.md). Models `Market` / `Selection` / `OddsQuote`, the deterministic `market_id`, and the `MarketCategory` / `MarketScope` / `SelectionType` enums all stay as they are. Only the upstream parser changes.

**Markets covered out of the gate:** universal (MONEYLINE, SPREAD, TOTAL) for every active league + sport-specific extensions documented in §6. **No player props** (consistent with sofa plans).

**Scope:** in this plan we (a) define how an SGO `oddID` decomposes into our `(category, type, scope, line, side)` tuple, (b) replace `core/event/odds/normalize.py` with an SGO-aware version, (c) keep `Market` / `Selection` / `OddsQuote` shapes, (d) add a small odds-format helper (American → decimal). Player-prop seeding and bookmaker-segregation are deferred.

---

## 1. What stays vs. what changes

| Component | Stays | Changes |
|---|---|---|
| `MarketCategory` enum | ✅ MONEYLINE / SPREAD / TOTAL / PROPS_GAME / PROPS_TEAM | — |
| `MarketScope` enum | ✅ FULL_GAME / H1 / H2 / Q1–Q4 / OVERTIME / P1–P3 / SHOOTOUT | + new value `INNINGS_1_5` (MLB), `ROUND` (boxing/UFC future) — see §6 |
| `SelectionType` enum | ✅ HOME / AWAY / DRAW / OVER / UNDER / YES / NO / 1X / X2 / 12 / NO_GOAL / CUSTOM | + new values `EVEN`, `ODD` (for `eo` betType) |
| `Market` model | ✅ same fields | `provider` default flips to `sportsgameodds`; `provider_market_id` becomes the SGO `oddID` (str), `provider_choice_group` becomes free for sport-specific use |
| `Selection` model | ✅ same fields | **PK changes from BigInt to CharField** (SGO has no `sourceId` analog; we'll synthesize `{event_id}:{oddID}`) |
| `OddsQuote` model | ✅ same | — (time-series of fair-odds movement; one row per movement detection) |
| `Bookmaker` model | 🆕 **new** | per [refactor-plan.md §3.5](refactor-plan.md). Seeded from `links.bookmakers` keys + `byBookmaker` keys at ingest. |
| `BookmakerSelection` model | 🆕 **new** | per [refactor-plan.md §3.6](refactor-plan.md). One row per `(Selection, Bookmaker)`, current quote only. |
| `core/event/odds/taxonomy.py` (`SOFASCORE_MARKET_MAP`) | ❌ **delete entirely** | replaced by a generic decomposer + a small per-betType mapping table |
| `core/event/odds/normalize.py` (`ingest_odds`) | renamed `ingest_odds_sofa`; sibling `ingest_odds_sgo` introduced | new entry point reads SGO's structured fields |
| `classify_choice` per-sport rules (210+ lines in current normalize.py) | ❌ **delete most** | most disappear because SGO ships `sideID` already typed |

The fact that SGO returns `sideID="home"` instead of `name="1"` (soccer) or `name="(-0.25) Brighton & Hove Albion"` (Asian handicap) means we no longer hand-write parsers for each sport. **The taxonomy work shrinks from 200 LOC to ~30.**

---

## 2. The taxonomy map (replaces `SOFASCORE_MARKET_MAP`)

Two small lookup tables. That's it.

### 2.1 `BET_TYPE_TO_CATEGORY`

```python
# core/event/odds/sgo_taxonomy.py

BET_TYPE_TO_CATEGORY = {
    "ml":     "MONEYLINE",       # 2-way home/away
    "ml3way": "MONEYLINE",       # 3-way home/away/draw — soccer & some hockey markets
    "sp":     "SPREAD",          # spread / handicap / puck line / run line
    "ou":     "TOTAL",           # over/under
    "yn":     "PROPS_GAME",      # yes/no — BTTS, OT, etc.
    "eo":     "PROPS_GAME",      # even/odd
}
```

### 2.2 `PERIOD_TO_SCOPE`

```python
PERIOD_TO_SCOPE = {
    "game":  "FULL_GAME",
    "reg":   "FULL_GAME",        # regulation only — distinguished by market type, not scope
    "1h":    "H1",  "2h": "H2",
    "1q":    "Q1",  "2q": "Q2",  "3q": "Q3",  "4q": "Q4",
    "1p":    "P1",  "2p": "P2",  "3p": "P3",
    "ot":    "OVERTIME",
    "so":    "SHOOTOUT",         # hockey shootout
    "1st5":  "INNINGS_1_5",      # MLB — first 5 innings (new scope value, see §6.1)
    "1st3":  "INNINGS_1_3",      # MLB — new scope value
    "5min":  "MINUTES_5",        # basketball — first-5-minutes prop, new scope value
    "10min": "MINUTES_10",       # basketball — first-10-minutes prop, new scope value
    # extend in a one-line edit when SGO ships a new periodID
}
```

### 2.3 `SIDE_TO_SELECTION`

```python
SIDE_TO_SELECTION = {
    "home":  "HOME",
    "away":  "AWAY",
    "draw":  "DRAW",
    "over":  "OVER",
    "under": "UNDER",
    "yes":   "YES",
    "no":    "NO",
    "even":  "EVEN",
    "odd":   "ODD",
}
```

### 2.4 The decomposer

```python
def parse_odd_id(odd_id: str) -> dict:
    """Returns {statID, statEntityID, periodID, betTypeID, sideID} from a SGO oddID."""
    parts = odd_id.split("-")
    if len(parts) < 5:
        raise ValueError(f"Malformed oddID: {odd_id!r}")
    # Player props can have an embedded playerID containing dashes — but SGO's docs
    # show it as a single token in statEntityID position (e.g. LEBRON_JAMES_NBA).
    # If we ever see dashes inside a token, we'll handle here. For game/team props
    # only, the simple 5-tuple split works.
    stat_id, stat_entity, period, bet_type, side = parts[0], parts[1], parts[2], parts[3], parts[4]
    return {
        "statID": stat_id,
        "statEntityID": stat_entity,
        "periodID": period,
        "betTypeID": bet_type,
        "sideID": side,
    }
```

That replaces the entire `(sport_id, marketId, marketPeriod) → MarketSpec` table. **No per-sport rows.** A new league or new market type works as long as its `betTypeID` is in our table; otherwise we land in `CUSTOM` and log it.

---

## 3. From oddID to a `Market` row

The mapping rules:

```python
def market_spec_from_odd(odd: dict, event: Event) -> MarketSpec:
    p = parse_odd_id(odd["oddID"])
    category = BET_TYPE_TO_CATEGORY.get(p["betTypeID"])
    scope    = PERIOD_TO_SCOPE.get(p["periodID"], "FULL_GAME")

    # Subject — game-level vs. team-level vs. player-level (latter unused in v1)
    subject_team = None
    if p["statEntityID"] in ("home", "away"):
        # Default: team-position is just the side of a moneyline/spread/total — game-level.
        # Promote to PROPS_TEAM only when the stat is per-side AND the betType is OU/YN.
        # E.g. points-home-game-ou-over is "home team total points" → PROPS_TEAM
        if p["betTypeID"] in ("ou", "yn") and p["statID"] != "points":
            category = "PROPS_TEAM"
        if p["betTypeID"] == "ou" and p["statID"] in ("points", "goals", "runs"):
            # Per-side OU on a scoring stat → team total
            category = "PROPS_TEAM"
            subject_team = event.home_team if p["statEntityID"] == "home" else event.away_team

    # Type — synthesized from sport + statID + betType (no global enum table)
    type_str = f"{event.league_id}_{p['statID'].upper()}_{p['betTypeID'].upper()}"
    # e.g. NFL_POINTS_ML, NHL_GOALS_OU, MLS_GOALS_ML3WAY

    # Line value
    line = None
    if p["betTypeID"] == "sp":
        line = float(odd.get("fairSpread") or odd.get("bookSpread") or 0) if (odd.get("fairSpread") or odd.get("bookSpread")) else None
    elif p["betTypeID"] == "ou":
        line = float(odd.get("fairOverUnder") or odd.get("bookOverUnder") or 0) if (odd.get("fairOverUnder") or odd.get("bookOverUnder")) else None

    return MarketSpec(
        category=category,
        type=type_str,
        scope=scope,
        line=line,
        subject_team=subject_team,
        kind_slug=p["betTypeID"],   # used in the deterministic market_id
    )
```

The `MarketSpec.type` string is generated, not enumerated. That's the design pivot from sofa: **sport-specific types are `{LEAGUE}_{STAT}_{BETTYPE}`, generated on the fly**. Examples:

| oddID | category | type | scope | line |
|---|---|---|---|---|
| `points-home-game-ml-home` | MONEYLINE | `NFL_POINTS_ML` | FULL_GAME | null |
| `points-all-game-ou-over` | TOTAL | `NFL_POINTS_OU` | FULL_GAME | 44.5 |
| `points-home-game-sp-home` | SPREAD | `NFL_POINTS_SP` | FULL_GAME | -3.5 |
| `goals-all-reg-ml3way-draw` | MONEYLINE | `MLS_GOALS_ML3WAY` | FULL_GAME | null |
| `goals-home-game-ou-over` | PROPS_TEAM | `MLS_GOALS_OU` | FULL_GAME | 1.5 |
| `goals-all-game-yn-yes` | PROPS_GAME | `MLS_BTTS_YN` (custom hand-mapping for BTTS, see §6.2) | FULL_GAME | null |
| `goals-all-game-ou-over` | TOTAL | `NHL_GOALS_OU` | FULL_GAME | 6.5 |
| `runs-all-1st5-ou-over` | TOTAL | `MLB_RUNS_OU` | INNINGS_1_5 | 4.5 |
| `points-LEBRON_JAMES_NBA-game-ou-over` | (skipped — PROPS_PLAYER not enabled) | — | — | — |

**Filter rule:** when `parse_odd_id` returns a `statEntityID` that isn't in `{home, away, all}`, we skip — that's a player prop. One line gates all player-prop markets out of the system, as per scope.

---

## 4. Deterministic `market_id` (unchanged shape)

Same scheme as sofa odds-plan §5.2 — keeps the public ID format stable, so the API contract doesn't break:

```
{event_id}-{kind_slug}[-{scope_slug}][-{line}][-{side_slug}]
```

`kind_slug` becomes `betTypeID` directly (`ml`, `sp`, `ou`, `yn`, `eo`, `ml3way`). Examples:
- `mXCZTRJnbX8ib64z1h3D-ml-ft`
- `mXCZTRJnbX8ib64z1h3D-ou-ft-44_5`
- `mXCZTRJnbX8ib64z1h3D-sp-ft--3_5-home`

Note the event ID is now a string, so the slug uses it verbatim. The existing `build_market_id` helper takes a kwarg-only signature; only the input type changes.

---

## 5. Normalization pipeline — `ingest_odds_sgo`

New file: `core/event/odds/normalize_sgo.py` (keep the old one for one release cycle, then delete).

```python
# core/event/odds/normalize_sgo.py

from .sgo_taxonomy import (
    BET_TYPE_TO_CATEGORY, PERIOD_TO_SCOPE, SIDE_TO_SELECTION, parse_odd_id,
)

PROVIDER = "sportsgameodds"

def ingest_odds_sgo(event: Event, odds_payload: dict) -> int:
    """Walks the `odds: { oddID: {...} }` map embedded in an SGO event payload,
    upserts Market + Selection rows. Returns count of selections written."""
    now = timezone.now()
    written = 0

    # Group odds by their (kind, scope, line, side) tuple — each entry is one selection
    # of a market. Multiple oddIDs sharing all four go into the same Market row.
    groups: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for odd_id, odd in odds_payload.items():
        parts = parse_odd_id(odd_id)
        if parts["betTypeID"] not in BET_TYPE_TO_CATEGORY:
            continue
        if parts["statEntityID"] not in ("home", "away", "all"):
            # player prop — skipped per scope
            continue
        groups_key = _market_key(parts, odd, event)
        groups[groups_key].append((parts, odd))

    for key, members in groups.items():
        market = _upsert_market(key, members, event, now)
        for parts, odd in members:
            sel = _upsert_selection(parts, odd, market, now)
            if sel:
                written += 1

    return written
```

Helpers (sketch — full code lives in the file once written):

- `_market_key(parts, odd, event)` — hashes `(betType, period, line, statEntityID-when-team-prop)` to a stable string, used to group oddIDs that share a market row.
- `_upsert_market(key, members, event, now)` — runs `Market.objects.update_or_create(id=…, defaults={…})` exactly like the sofa version, but:
  - `provider="sportsgameodds"`, `provider_market_id=` first oddID in the group (any will do; debugging only).
  - `category, type, scope, line, subject_team` derived from the group's spec.
- `_upsert_selection(parts, odd, market, now)` — `Selection.objects.update_or_create(id=…, defaults={…})` with:
  - **`Selection.id = f"{market.id}:{parts['statEntityID']}-{parts['sideID']}"`** — deterministic string PK, replaces the BigInt SofaScore `sourceId`. Stable across refreshes.
  - `type = SIDE_TO_SELECTION.get(parts["sideID"], "CUSTOM")`.
  - `decimal_odds = american_to_decimal(odd["fairOdds"] or odd["bookOdds"])`.
  - `opening_decimal_odds = american_to_decimal(odd["openFairOdds"] or odd["openBookOdds"])`.
  - `movement = sign(opening_decimal_odds - decimal_odds)` — `-1` (drifted shorter), `0` (unchanged), `+1` (drifted longer).
  - `suspended = not odd.get("bookOddsAvailable")`.
  - `label = odd.get("marketName") or _humanize(parts, market)`.
  - **Time-series quote** still inserted only when `decimal_odds` differs from previous, same as sofa plan.
- After each Selection is written, **the settlement signal kicks in** — see [settlement-plan.md §3.1](settlement-plan.md). The provider-flag path that copied SofaScore's `winning: true/false` is replaced with a SGO-flavored variant that reads `odd.get("score")` against the line.
- Per-book quotes from `odd["byBookmaker"]` populate `BookmakerSelection` rows in the same loop:

```python
for book_id, book_data in (odd.get("byBookmaker") or {}).items():
    bookmaker, _ = Bookmaker.objects.get_or_create(id=book_id, defaults={"name": book_id.title()})
    BookmakerSelection.objects.update_or_create(
        selection=sel, bookmaker=bookmaker,
        defaults=dict(
            decimal_odds=american_to_decimal(book_data.get("odds")),
            spread=_parse_decimal(book_data.get("spread")),
            over_under=_parse_decimal(book_data.get("overUnder")),
            available=bool(book_data.get("available")),
            deeplink=book_data.get("deeplink") or "",
            last_updated_at=parse_datetime(book_data["lastUpdatedAt"]),
        ),
    )
```

This is a per-bookmaker upsert per Selection per ingest. On Amateur tier (≤9 bookmakers, ~50 selections per finalized event) that's ~450 small upserts per ingest — well within Postgres's comfort zone. Wrap each event's ingest in `transaction.atomic()` to keep it tight.

### 5.1 Odds format helpers

```python
# core/event/odds/odds_format.py

def american_to_decimal(s: str | None) -> Decimal | None:
    if s is None or s == "":
        return None
    n = int(s)  # SGO returns "+130", "-150", etc.
    if n > 0:
        return Decimal(n) / 100 + 1
    if n < 0:
        return Decimal(100) / abs(n) + 1
    return Decimal("1.0")

def decimal_to_american(d: Decimal) -> int:
    if d >= 2:
        return int(round((d - 1) * 100))
    return int(round(-100 / (d - 1)))
```

These replace `fractional_to_decimal` from the sofa codebase. The DB stays in decimal as before; American is computed on the fly for the API response.

---

## 6. Sport-specific markets we want from day 1

The decomposer in §3 generates types like `NFL_POINTS_ML` automatically. For most markets that's enough — the front end groups by `(category, type, scope)`, doesn't care about the `type` string itself beyond rendering.

The ones below need an explicit override because the auto-generated type would be ambiguous or misleading.

### 6.1 MLB (Baseball)

| Display | oddID example | Auto type | Override type |
|---|---|---|---|
| Run line | `runs-home-game-sp-home` | `MLB_RUNS_SP` | `MLB_RUN_LINE` |
| Total runs | `runs-all-game-ou-over` | `MLB_RUNS_OU` | (keep auto) |
| Money line | `runs-home-game-ml-home` | `MLB_RUNS_ML` | (keep auto — but `runs` not `points`, so already distinct) |
| 1st 5 innings ML | `runs-home-1st5-ml-home` | `MLB_RUNS_ML` | `MLB_RUNS_ML_1ST5` (qualified by scope) |
| 1st 5 innings total | `runs-all-1st5-ou-over` | `MLB_RUNS_OU` | `MLB_RUNS_OU_1ST5` |

**New scope values needed:** `INNINGS_1_5`, `INNINGS_1_3`. Already added to `PERIOD_TO_SCOPE` (§2.2) — also need a one-line addition to the `MarketScope` enum class (model migration).

### 6.2 Soccer (MLS, UEFA Champions League)

| Display | oddID example | Type |
|---|---|---|
| 3-way moneyline | `goals-home-reg-ml3way-home` (and `-draw`, `-away`) | `{LEAGUE}_GOALS_ML3WAY` (auto OK) |
| Asian handicap | `goals-home-reg-sp-home` | `{LEAGUE}_GOALS_SP` (auto OK) |
| Total goals | `goals-all-reg-ou-over` | `{LEAGUE}_GOALS_OU` (auto OK) |
| Both teams to score | `goals-all-game-yn-yes` | **override → `{LEAGUE}_BTTS`** |
| Team total goals | `goals-home-reg-ou-over` | promotes to `PROPS_TEAM`, type `{LEAGUE}_TEAM_GOALS_OU` |
| Double chance | `goals-{home|away|draw}-reg-ml3way-{1X|X2|12}` | (if SGO ships these — verify in live probe) |

The BTTS override is a single row in a small `TYPE_OVERRIDES` map:

```python
TYPE_OVERRIDES = {
    # (statID, statEntityID, periodID, betTypeID, sideID)  →  fixed type string
    ("goals", "all", "game", "yn", "yes"): lambda lg: f"{lg}_BTTS",
    ("goals", "all", "game", "yn", "no"):  lambda lg: f"{lg}_BTTS",
    # add more as we encounter them
}
```

Tiny, additive, no migrations.

### 6.3 NHL (Hockey)

| Display | oddID example | Type |
|---|---|---|
| Money line (incl OT) | `goals-home-game-ml-home` | `NHL_GOALS_ML` (auto OK) |
| Money line (regulation 3-way) | `goals-home-reg-ml3way-{home|draw|away}` | `NHL_GOALS_ML3WAY_REG` — distinguish via `scope=FULL_GAME` + `type` qualifier |
| Puck line (spread) | `goals-home-game-sp-home` | **override → `NHL_PUCK_LINE`** |
| Total goals | `goals-all-game-ou-over` | `NHL_GOALS_OU` (auto OK) |
| Period winner | `goals-home-1p-ml-home` | `NHL_GOALS_ML` with `scope=P1` |
| Period total | `goals-all-1p-ou-over` | `NHL_GOALS_OU` with `scope=P1` |
| Shootout | `goals-home-so-ml-home` | `NHL_GOALS_ML` with `scope=SHOOTOUT` |

The hockey-specific market types (`NHL_PUCK_LINE`, `NHL_MATCH_WINNER_INC_OT`) from the sofa hockey-extension plan are no longer separately enumerated — the `(scope, type)` pair carries the same meaning.

### 6.4 NFL / NCAAF (Football)

| Display | oddID | Type |
|---|---|---|
| Money line | `points-home-game-ml-home` | `NFL_POINTS_ML` |
| Spread | `points-home-game-sp-home` | `NFL_POINTS_SP` |
| Total | `points-all-game-ou-over` | `NFL_POINTS_OU` |
| Q1 / Q2 / H1 versions | with `periodID=1q` / `2q` / `1h` | same type, different scope |
| Team total points | `points-home-game-ou-over` | `PROPS_TEAM`, `NFL_TEAM_POINTS_OU` |

### 6.5 NBA / NCAAB (Basketball)

Same shape as NFL with `points` stat. Adds:
| Display | oddID | Type |
|---|---|---|
| Q1–Q4 ML/SP/OU | with periodID `1q`/`2q`/`3q`/`4q` | scope-qualified |
| H1/H2 | periodID `1h`/`2h` | scope-qualified |
| First 5 / 10 minutes | periodID `5min` / `10min` | new scope values `MINUTES_5` / `MINUTES_10` |

---

## 7. Caching & API call policy (mostly unchanged)

[Sofa odds-system-plan §6](../sofa/odds-system-plan.md#6-api-refactor-strategy) carries over — same Redis topology, same per-event freshness tiers, same per-event refresh cap. The differences:

| Concern | Sofa | SGO |
|---|---|---|
| Per-event call cost | 1 call to `/matches/get-all-odds` | 1 call to `/v2/events?eventID=` |
| Cost per call | 1 toward 500/mo | ~1 object toward 2.5k/mo |
| Per-event refresh cap | 10/mo | 8/mo (slightly tighter; 320 / 50 active events ≈ 6, with margin) |
| Cache key prefix | `sofascore:…` | `sgo:…` |
| Live cache TTL | 30s | 30s — but consider 60s since SGO updates upstream every 10 min anyway |

The Flutter / REST contract from sofa odds-plan §8 is **unchanged**. Endpoints, query parameters, and response shape are wire-compatible. The internal `provider` field on `Market` flips from `sofascore` to `sportsgameodds` — invisible to clients.

---

## 8. Migration order

1. **Add the helpers** [core/event/odds/odds_format.py](../../core/event/odds/odds_format.py) and [core/event/odds/sgo_taxonomy.py](../../core/event/odds/sgo_taxonomy.py). No callers yet.
2. **Migrate `Selection.id`** from `BigIntegerField` to `CharField(max_length=128, primary_key=True)`. Wipes existing Selection rows; dev DB acceptable. Same migration adds the new `MarketScope` enum values (`INNINGS_1_5`, `INNINGS_1_3`, `MINUTES_5`, `MINUTES_10`) and `SelectionType` values (`EVEN`, `ODD`).
3. **Add `core/event/odds/normalize_sgo.py`** with `ingest_odds_sgo`. Unit-test against a captured fixture — pull a real SGO event payload via the new client and dump it to `event-tests/fixtures/sgo_*.json`.
4. **Wire `EventCron.ingest_league` to call `ingest_odds_sgo`** (per [refactor-plan.md §4](refactor-plan.md)).
5. **Settlement provider path swap** — see [settlement-plan.md §3.1](settlement-plan.md).
6. **Delete** `core/event/odds/normalize.py` and `core/event/odds/taxonomy.py` after one stable week.

Each step is independently shippable; #2 is the only one that wipes data.

---

## 9. Open questions / probes to run with first real key

These need a live API key to validate; placeholder defaults in code are safe.

1. **Does SGO ship `score` on every odd post-finalization, or only on certain stat types?** Probe: pull a `finalized=true` event and check coverage. Drives [settlement-plan.md §2.1](settlement-plan.md).
2. **Are MLS / UCL `ml3way` and `sp` markets keyed on `periodID="reg"` or `periodID="game"`?** The docs hint at "Regulation" being a separate period — verify with a live response.
3. **Does NCAAB ship `5min` / `10min` periods?** Affects whether the new scope values are useful.
4. **Player-prop oddIDs** — the docs say `playerID` can sit in `statEntityID` like `LEBRON_JAMES_NBA`. Confirm shape before we ever turn PROPS_PLAYER on.
5. **Does the response count player-prop odds toward the object quota separately?** Critical for the budget.
6. **`includeAltLines=true` cost** — by how much does the response grow? If alt lines double the object count, leave that flag off.

Each can be answered with one or two `curl` calls and a glance at `/account/usage/`. Plan for a probe day before the cutover commit.

---

**This plan is intentionally smaller than the sofa odds-system plan.** The bulk of normalization complexity in SofaScore came from parsing free-text choice names — SGO's typed `oddID` shape eliminates that. We trade ~200 LOC of `classify_choice` rules for ~30 LOC of dictionaries plus a `parse_odd_id` splitter. Sport-specific extensions land as additive map entries, never as new code paths.
