# API Inventory — SofaScore (current) → SportsGameOdds (target)

This is the call-by-call swap sheet. The **old** column is what's running on `main` today (post-sofa migration); the **new** column is the SportsGameOdds endpoint that replaces it. Source of truth for the old side: [api-switch/sofa/old-api-calls.md](../sofa/old-api-calls.md) plus the live audit (the sofa migration shipped — see [refactor-plan.md §0](refactor-plan.md) for the baseline).

**Provider docs root:** https://sportsgameodds.com/docs/
**Base URL:** `https://api.sportsgameodds.com/v2/`
**Auth:** `X-Api-Key: $SPORTSGAMEODDS_API_KEY` header (or `?apiKey=…` query param).

---

## 0. The big shape change

SofaScore needed **two calls per event** to populate our DB: one for the schedule (`/tournaments/get-scheduled-events`) and one for each event's odds (`/matches/get-all-odds`). SportsGameOdds collapses that into **one call per league**: `GET /events?leagueID=NFL&startsBefore=…&startsAfter=…&oddsAvailable=true` returns events **with embedded teams, status, results, and odds keyed by `oddID`**. That single shape change drives most of the simplification in [refactor-plan.md](refactor-plan.md) and [odds-system-plan.md](odds-system-plan.md).

---

## 1. Sports / leagues seed

### Old (current)
- **File:** [core/event/management/commands/seed_sports.py](../../core/event/management/commands/seed_sports.py) (one-shot — `sportUpdate.py` is a deprecated shim).
- **Call:** `GET https://sofascore.p.rapidapi.com/sports/list?countryCode=`
- **Persists to:** `Sport` model — `id` (int PK), `slug`, `name`, `active`.

### New
- **Call:**
  ```
  GET https://api.sportsgameodds.com/v2/sports/
  GET https://api.sportsgameodds.com/v2/leagues/
  ```
- **Persists to:** `Sport` (BASEBALL / BASKETBALL / FOOTBALL / HOCKEY / SOCCER) **+ a new `League` model** keyed on `leagueID` string with FK to `Sport`. See [refactor-plan.md §3](refactor-plan.md).
- **Cadence:** one-shot. The list is closed enum-style (changes only when SGO adds a league); replace `seed_sports` with `seed_sports_leagues` and run on deploy.
- **Allowlist for Amateur tier (free):** `MLB, NBA, NCAAB, NCAAF, NFL, NHL, MLS, UEFA_CHAMPIONS_LEAGUE`. Set `League.active=True` for those, everything else `active=False` (so we can flip new leagues on without code changes when we upgrade tiers).

---

## 2. Event ingest (the recurring cron)

### Old (current)
- **File:** [core/event/crons/eventUpdate.py](../../core/event/crons/eventUpdate.py).
- **Call (per active sport):** `GET /tournaments/get-scheduled-events?categoryId={sport_id}` — with a live-events fallback for sport_id=4 (ice hockey) when scheduled is empty.
- **Cadence:** Celery beat `event_cron`, every 12h.
- **What it does:** upserts `Event` rows + `Team` rows (teams embedded in event payload, zero extra calls).

### New
- **Call (per active league — not per sport):**
  ```
  GET /v2/events
      ?leagueID=NFL
      &startsAfter=<now-2h>
      &startsBefore=<now+7d>
      &oddsAvailable=true
      &limit=100
      &cursor=<nextCursor when paginating>
  ```
- **One call per league per tick.** A league's worth of events comes back with `teams.home`, `teams.away`, `status`, `results`, and `odds` (keyed by `oddID`) all embedded. **No second odds call needed** — settlement-grade data ships in the same payload.
- **Pagination:** cursor-based. Response carries `nextCursor`; call again with `cursor=<that>` until empty.
- **Cadence:** beat `event_cron`, **every 6h** (Amateur tier updates upstream every 10 min anyway, and the per-minute throttle is 10 req/min — see budget in [refactor-plan.md §1](refactor-plan.md)).
- **Persists to:** `Event` (PK = `eventID` string), `Team` (PK = `(league, teamID)`), `Market`, `Selection`, `OddsQuote` — all in one ingest pass.

### Response envelope
```json
{
  "success": true,
  "nextCursor": "eyJhbGciOiJIUzI1NiJ9...",
  "data": [ /* event objects */ ]
}
```

### Event object (fields we consume)
```jsonc
{
  "eventID":  "mXCZTRJnbX8ib64z1h3D",     // string PK
  "sportID":  "FOOTBALL",                  // enum
  "leagueID": "NFL",                       // enum
  "type":     "match",
  "teams": {
    "home": { "teamID": "...", "names": {"long":"...", "medium":"...", "short":"..."},
              "colors": {"primary":"#…","secondary":"#…","primaryContrast":"#…","secondaryContrast":"#…"},
              "statEntityID": "home" },
    "away": { /* same shape */ }
  },
  "status": {
    "started": false, "completed": false, "cancelled": false, "ended": false,
    "live": false, "delayed": false, "finalized": false,
    "currentPeriodID": null, "previousPeriodID": null,
    "displayShort": "...", "displayLong": "...",
    "inBreak": false, "hardStart": true,
    "periods": { "started": [], "ended": [] },
    "oddsPresent": true, "oddsAvailable": true,
    "startsAt": "2025-09-08T20:20:00Z",
    "previousStartsAt": []
  },
  "info":   { "seasonWeek": "NFL Wk1", /* league-specific */ },
  "links":  { "bookmakers": { "draftkings":"…", "fanduel":"…" } },
  "odds":   { /* keyed by oddID — see §3 */ },
  "results": { /* empty pre-game, populated when finalized */ },
  "players": { /* roster keyed by playerID */ }
}
```

### Field-by-field mapping to our `Event` model
See [refactor-plan.md §3.3](refactor-plan.md). Highlights:
- `Event.id` ← `eventID` (CharField PK, was BigInt under SofaScore — **breaking change**).
- `Event.sport_id` ← `sportID` (FK to `Sport`).
- `Event.league_id` ← `leagueID` (FK to new `League` model).
- `Event.start_time` ← `status.startsAt` (parse ISO).
- `Event.status_type` derived from the four booleans:
  - `cancelled=true` → `"canceled"`
  - `ended=true && finalized=true` → `"finished"`
  - `live=true` → `"inprogress"`
  - else → `"notstarted"`
- `Event.completed` ← `status.ended && status.finalized`.
- `Event.home_team` / `away_team` — FK to `Team` after upsert from `teams.home/.away`.
- `Event.home_score` / `away_score` — derived from a fixed odd's `score` field (e.g. `points-home-game-ml-home`.score) once `finalized=true`. See [settlement-plan.md §2](settlement-plan.md).

---

## 3. Odds (now part of the event payload)

### Old (current)
- **File:** [core/event/sofascore.py:get_match_odds](../../core/event/sofascore.py) called from [core/event/odds/normalize.py:ingest_odds](../../core/event/odds/normalize.py).
- **Call:** `GET /matches/get-all-odds?matchId={event_id}` — **one call per event we want odds for.**
- **Cadence:** mostly on-demand (user opens an event detail page) plus the `warm_upcoming_odds_cron` 30-min warmer.

### New
- **No separate call.** `GET /v2/events?…&oddsAvailable=true` already returns each event with `odds: { oddID: {...}, oddID: {...} }`.
- **For a refresh of a single event** (user opens detail page): `GET /v2/events?eventID={eventID}&includeOpposingOdds=true` returns just that event with current odds. Same envelope, `data` has one row.
- **Optional filters** to keep response size sane:
  - `oddID=points-home-game-ml-home,points-away-game-ml-away,points-all-game-ou-over,…` — fetch only the markets we care about.
  - `includeOpposingOdds=true` — auto-include the matching `opposingOddID` for each requested oddID.
  - `bookmakerID=draftkings,fanduel` — restrict the per-book breakdown.
  - `includeAltLines=true` — include alt spreads/totals (skip in v1).
  - `expandResults=true` — include all stat values on results.
  - `includeOpenCloseOdds=true` — include `openFair*` / `openBook*` / `closeFair*` / `closeBook*`. We need this to populate `Selection.opening_decimal_odds` and (post-game) `closeOverUnder` for settlement.

### A single `odds[oddID]` entry
```jsonc
{
  "oddID":         "points-home-game-ml-home",
  "opposingOddID": "points-away-game-ml-away",
  "marketName":    "Moneyline",
  "statID":        "points",
  "statEntityID":  "home",                    // or "away" | "all" | "<playerID>"
  "periodID":      "game",                    // or "reg" | "1h" | "2h" | "1q"…"4q" | "1p"…"3p" | "ot" | "so"
  "betTypeID":     "ml",                      // ml | ml3way | sp | ou | yn | eo
  "sideID":        "home",                    // home | away | draw | over | under | yes | no | even | odd

  "started": false, "ended": false, "cancelled": false,

  "fairOddsAvailable": true,  "bookOddsAvailable": true,
  "fairOdds":      "-143",    "bookOdds":      "-150",      // American format strings
  "fairSpread":    "+1.5",    "bookSpread":    "+1.5",      // sp only
  "fairOverUnder": "44.5",    "bookOverUnder": "44.5",      // ou only

  "openFairOdds":  "+120", "openBookOdds":  "+115",
  "openFairSpread":"+2.0", "openBookSpread":"+2.5",
  "openFairOverUnder":"43.5", "openBookOverUnder":"43.5",

  "scoringSupported": true,

  "byBookmaker": {
    "draftkings": { "odds":"-150", "spread":"+1.5", "overUnder":null,
                    "lastUpdatedAt":"2025-09-08T18:32:11Z", "available":true,
                    "deeplink":"https://…" },
    "fanduel":    { "odds":"-145", … }
  },

  // Post-game additions (when status.finalized=true):
  "score": 27   // numeric — see settlement-plan.md
}
```

### oddID composition rule (the whole taxonomy in one line)
```
oddID = "{statID}-{statEntityID}-{periodID}-{betTypeID}-{sideID}"
```
This maps **directly** onto our existing `Market.category / scope / type / side` schema. The Sofa-era `SOFASCORE_MARKET_MAP` table goes away — see [odds-system-plan.md §4](odds-system-plan.md).

---

## 4. Per-event refresh (replaces SofaScore's `get_match_odds`)

### Old
- `get_match_odds(match_id)` per event detail-page hit, with Redis cache + 12-hour cap.

### New
- **Same UX, simpler call:** `GET /v2/events?eventID={id}&includeOpenCloseOdds=true` — one round trip; everything returns. Cache layer stays the same.
- The freshness tiers from [sofa odds-system-plan.md §6.2](../sofa/odds-system-plan.md) still apply (pre-match >24h: 6h TTL; <24h: 30 min; live: 30s) — they're cheaper to honor now because each call returns a whole event, not just odds, so a refresh updates `status` / `results` for free.

---

## 5. Team search — **deleted**

### Old
- `GET https://sofascore.p.rapidapi.com/teams/search?name=…` and `GET …/teams/get-logo?teamId=…` were already removed in the sofa migration (teams are upserted from embedded payloads).

### New
- **Same — no team-search endpoint at all.** Every team appears embedded in the event response (`teams.home`, `teams.away`) with name, colors, statEntityID. Logos: SGO doesn't ship binary logos; if we want them, we hotlink the team's color-rendered avatar or fetch from a public CDN later. `Team.logo_url` stays nullable.
- **Per-league team scoping (new):** SGO docs note teams are per-league — e.g., `ARSENAL_EPL` vs `ARSENAL_UEFA_CHAMPIONS_LEAGUE` are two team rows for the same physical club. Our `Team` PK becomes a composite or a CharField storing the SGO `teamID` directly with `(league, teamID)` uniqueness. See [refactor-plan.md §3.2](refactor-plan.md).

---

## 6. Account usage (new — replaces our Redis monthly counter)

### Old
- We maintain `sofascore:calls:{YYYY-MM}` Redis counter, soft cap 480 / hard cap 500.

### New
- **Server-side counters from the provider:** `GET /v2/account/usage/` returns our object & request usage for the current cycle. We mirror it into a Redis cache hit hourly so dashboards / debugging panels can read without burning a request.
- **Local guard rail still useful** — keep a local counter for the per-minute throttle (10 req/min on Amateur), implemented as a token bucket on the client. The monthly cap (2.5k objects/mo) is too coarse to enforce client-side cleanly; instead, keep a `last_seen_usage` snapshot from `/account/usage/` and refuse calls when objects-used / objects-allotted > 0.95.

---

## 7. Endpoints we don't use (yet)

| Endpoint | When we'd want it | Status |
|---|---|---|
| `GET /v2/teams/` | Standalone team detail (logos, depth chart) | Not needed v1 — embedded in events. |
| `GET /v2/players/` | Player props, headshots | Out of scope (no PROPS_PLAYER, consistent with sofa plans). |
| `GET /v2/stats/` | Per-game stat lines, box scores | Future (live boxscore feature). |
| `GET /v2/markets/` | Browse the universe of supported markets | Useful for the taxonomy seed in [odds-system-plan.md §4.4](odds-system-plan.md), once. |

---

## 8. Cross-cutting behavior changes

| Concern | SofaScore (today) | SportsGameOdds (target) |
|---|---|---|
| Auth | `X-RapidAPI-Key` + `X-RapidAPI-Host` | Single `X-Api-Key` header |
| Quota model | 500 calls / month (hard) | 10 req/min + 2.5k objects/mo (Amateur) |
| Odds format | Fractional strings (`"10/11"`) | American strings (`"-110"`) |
| Event ID | BigInt (SofaScore numeric) | String (SGO opaque, e.g. `mXCZTRJnbX8ib64z1h3D`) |
| Team ID | Int per global team | String, **per-league** scoped |
| Per-event odds call | Yes (`get-all-odds`) | No — embedded in event response |
| Pagination | None (per-sport bulk) | Cursor (`nextCursor`) |
| Settlement signal | Provider `winning: true/false` on choices | `score` value per odd + `status.finalized` |
| Bookmaker rows | None (we collapsed) | New `Bookmaker` + `BookmakerSelection` tables — per-book deeplinks/prices for the UI; settlement still uses `fairOdds` |
| Sport allowlist | `Sport.active` | `League.active` (one level deeper) |

---

## 9. Refactor checklist (high-level — full plan in [refactor-plan.md](refactor-plan.md))

1. New env var `SPORTSGAMEODDS_API_KEY`. Keep `RAPID_API_KEY` for one release as fallback.
2. New `core/event/sportsgameodds.py` client — cursor-aware, token-bucket throttled (10/min), reads `/account/usage/` snapshot for the soft cap.
3. New `League` model + `Sport` adjustment (string PK, enum-like). Migration wipes existing Sport rows; dev DB acceptable.
4. `Event.id` and `Team.id` switch to CharField — **breaking** for `Game.event` FK and `Selection` PKs downstream. See [game-match-audit-plan.md](game-match-audit-plan.md) for downstream-only impacts (the Game/Match refactor itself was already shipped).
5. Replace `SOFASCORE_MARKET_MAP` with a generic `parse_oddID()` + small per-betType taxonomy table. See [odds-system-plan.md §4](odds-system-plan.md).
6. Drop the `winning`-flag provider path; replace with `score`-driven settlement (still PROVIDER source — same enum). See [settlement-plan.md](settlement-plan.md).
7. Rename Celery beat: `event_cron` cadence to 6h; `warm_upcoming_odds_cron` cadence to 30 min stays.
8. Delete the live-events fallback (no longer needed — SGO returns scheduled and live in one feed via `live=true|false` filters).

That's the inventory. The rest of the plans build on this mapping.
