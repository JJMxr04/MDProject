# Refactor Plan — Events, Teams, Leagues on SportsGameOdds

**Provider:** SportsGameOdds — https://sportsgameodds.com/docs/
**Tier:** Amateur (free) — 10 req/min, 2.5k objects/month, 8 leagues across 5 sports.
**Allowlist (locked at start):** `MLB, NBA, NCAAB, NCAAF, NFL, NHL, MLS, UEFA_CHAMPIONS_LEAGUE`.
**Architecture must support adding more leagues / sports without code changes** — see [league-extension-plan.md](league-extension-plan.md).
**Builds on:** the completed sofa migration. `Sport`, `Team`, `Event`, `Market`, `Selection`, `OddsQuote`, settlement engine, and the Game/Match refactor are all live (see [audit summary](#0-current-baseline)). This plan rewires the **provider boundary**, not the downstream models or scoring.

---

## 0. Current baseline

What's already shipped (do not re-plan):
- Models: `Sport(int PK)`, `Team(int PK)`, `Event(BigInt PK, FKs to Sport+Team)`, `Market(string PK, deterministic)`, `Selection(BigInt PK, settlement enums)`, `OddsQuote`. Files in [core/event/models/](../../core/event/models/).
- Settlement engine: [core/event/odds/settlement.py](../../core/event/odds/settlement.py) — provider/computed/manual sources; PENDING/WON/LOST/PUSH/VOID enum.
- Game/Match refactor: [core/match/scoring.py](../../core/match/scoring.py) — pure-function scoring off `Selection.settlement_status`. `Game.match` is a real FK; `Bet` has no settlement booleans, only snapshot odds.
- Beat schedule: `event_cron` (12h), `warm_upcoming_odds_cron` (30min), `settle_pending_cron` (nightly), `complete_matches_cron` (daily).

What changes here: the SofaScore client is replaced with a SportsGameOdds client; `Sport`/`Team`/`Event` PKs change from int/BigInt to string; a new `League` table sits between `Sport` and `Event`. Models keep the same downstream contracts (FK targets exist; field names where downstream code reads them are preserved or aliased).

---

## 1. Budget math (Amateur tier)

The two ceilings:
- **10 requests/minute** — easy. 600/hour, 14400/day, 432k/month theoretical max if we burned every minute. We won't get close.
- **2.5k objects/month** — the real constraint. `GET /events` returns rows in `data[]`; each row is presumed to count as 1 object. Embedded odds inside an event don't count separately based on the docs language ("2.5k objects per month") — but we'll **assume worst case**: each event row = 1 object regardless of `?expandResults` or `?includeOpenCloseOdds`, **and** confirm by reading `/account/usage/` after the first ingest pass. If the meter ticks faster than expected, we throttle.

### Cron cost — events ingest only

`S` = active leagues, `T` = ticks/day. Monthly = `S × T × 30 × pages_per_call`.

For Amateur, `S = 8`. NFL has ~16 games/week → one page; NBA on a busy night has ~10 games → one page; NCAAF/NCAAB can have 50+ teams playing → potentially 2 pages of 100. Worst case **2 pages × 8 leagues × T × 30**.

| Option | Ticks/day | Interval | Calls/month | Objects/month (worst case 2 pages × 100 events) |
|---|---|---|---|---|
| **A — every 12h** | 2 | 12h | 480 | up to 96k objects (capped to whatever events actually exist; in season ~1500–2200) |
| **B — every 6h** | 4 | 6h | 960 | up to 192k worst case; realistic ~3000–4400 |
| **C — every 4h** | 6 | 4h | 1440 | realistic ~4500–6600 — **over** |

**Realistic count of events per league per day** (in-season, looking 7 days ahead):
- NFL: ~16/week → 16 events/day at peak window.
- NBA / NHL / MLB: 5–15 games/day during their seasons.
- NCAAF / NCAAB: 30–80 games/day on game days.
- MLS: 5–10 games/week.
- UEFA Champions League: 8–16 games on matchdays, otherwise 0.

So a daily window of "next 7 days" has order-of 100–400 events live across the 8 leagues — **most of them stable** (rosters, start times, lines drift). Re-fetching each one 4× a day costs 400–1600 objects/day → **way over** if we're naive.

### Strategy that fits 2.5k objects/month

1. **Tight time window:** `startsAfter=now-2h`, `startsBefore=now+72h`. Seven days is overkill — 3 days of lookahead covers UI needs without re-billing for the same future event 14 times before it starts.
2. **Two-pass ingest:**
   - **Schedule pass** (cheap): `oddsAvailable=false` if needed to get just the upcoming-events skeleton. Currently `/v2/events` doesn't differentiate cost by query — but combined with `oddID` filter (only the markets we care about) we'll typically pull 1 odd per event in the schedule pass.
   - **Odds pass** (per event, on demand): one `?eventID=` call when a user opens the detail page or when a Bet is placed against the event.
3. **Static-event short-circuit:** if `Event.start_time > now + 24h` and we updated it within the last 12h, skip re-fetch. Keep a `last_provider_refresh_at` timestamp on `Event`.
4. **Live-only mode for in-progress events:** during a live window, use `live=true` filter — only events currently happening come back. Cheap.

### Recommended cron cadence

| Cron | Cadence | Estimated objects/mo |
|---|---|---|
| `events_schedule_cron` (per-league, 72h window) | every 6h | ≈ 8 leagues × 4 ticks/day × 30 days × ~10 events avg = **9600** ❌ over |

That's still over budget on naive math. **Mitigation: per-league cadence varies.**

| League | Avg events / day in 72h window | Cadence | Objects/mo |
|---|---|---|---|
| NFL | ~5 (16 games/week) | every 12h | 5 × 2 × 30 = 300 |
| NBA | ~12 in season, 0 off | every 6h | 12 × 4 × 30 × 0.6 (in-season fraction) = ~860 |
| MLB | ~15 in season, 0 off | every 12h | 15 × 2 × 30 × 0.55 = ~500 |
| NHL | ~12 in season, 0 off | every 12h | 12 × 2 × 30 × 0.55 = ~400 |
| NCAAF | ~25 game-days only | once on game day | ~150 |
| NCAAB | ~40 game-days only | once on game day | ~600 — risky |
| MLS | ~3 in season, 0 off | every 24h | 3 × 1 × 30 × 0.6 = ~55 |
| UCL | ~10 on matchdays only | once on matchday | ~50 |

Rough total **≈ 2900 — still slightly over.** Pull NCAAB to once on game day at game time and NBA to every 12h: get to **~2200**, leaving ~300 objects/mo for on-demand `eventID=` refreshes.

**This is the real plan: per-league cadence, configurable.** Implemented via a `League.refresh_cadence_minutes` field defaulting to 720 (12h) with NCAAB / UCL / NCAAF set to 1440 (24h) and NBA to 360 (6h, in season). The scheduler reads this; one Celery beat job per league is unmanageable, so use a single beat that walks `League.objects.filter(active=True)` and decides per-row whether to fetch based on `last_refreshed_at`.

### Safety valve

A Redis token bucket on the client (10 tokens, 1 token / 6s refill) blocks any over-rate burst. A second monthly counter `sgo:objects:{YYYY-MM}` mirrors `/account/usage/`'s `objectsUsed`; the client refuses calls when `objectsUsed / objectsAllotted > 0.95` with a loud log. One safety wrapper, two failure modes covered.

---

## 2. Single-tier client architecture

Replace [core/event/sofascore.py](../../core/event/sofascore.py) with [core/event/sportsgameodds.py](../../core/event/sportsgameodds.py).

```python
# core/event/sportsgameodds.py

class SportsGameOddsClient:
    BASE = "https://api.sportsgameodds.com/v2"
    BUCKET_KEY = "sgo:bucket"
    OBJECTS_KEY = "sgo:objects:{ym}"
    HARD_PCT = 0.95

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ["SPORTSGAMEODDS_API_KEY"]
        self.session = requests.Session()
        self.session.headers["X-Api-Key"] = self.api_key

    # Public methods --------------------------------------------------------

    def get_events(self, *, league_id, starts_after=None, starts_before=None,
                   live=None, finalized=None, odds_available=True,
                   odd_ids=None, include_open_close=True, limit=100):
        """Cursor-paginated. Yields events one at a time across pages."""
        params = self._params(league_id=league_id, startsAfter=starts_after,
                              startsBefore=starts_before, live=live,
                              finalized=finalized, oddsAvailable=odds_available,
                              oddID=",".join(odd_ids) if odd_ids else None,
                              includeOpenCloseOdds=include_open_close,
                              limit=limit)
        cursor = None
        while True:
            if cursor: params["cursor"] = cursor
            payload = self._request("GET", "/events", params)
            for ev in payload.get("data", []):
                yield ev
            cursor = payload.get("nextCursor")
            if not cursor: return

    def get_event(self, event_id: str, *, include_open_close=True):
        params = self._params(eventID=event_id, includeOpenCloseOdds=include_open_close,
                              includeOpposingOdds=True)
        payload = self._request("GET", "/events", params)
        rows = payload.get("data", [])
        return rows[0] if rows else None

    def get_account_usage(self):
        return self._request("GET", "/account/usage", {})

    def get_sports(self):  return self._request("GET", "/sports", {}).get("data", [])
    def get_leagues(self): return self._request("GET", "/leagues", {}).get("data", [])

    # Internal --------------------------------------------------------------

    def _request(self, method, path, params):
        self._consume_token()
        self._check_object_cap()
        r = self.session.request(method, self.BASE + path, params={k:v for k,v in params.items() if v is not None})
        if r.status_code == 429:
            time.sleep(6); return self._request(method, path, params)
        r.raise_for_status()
        return r.json()

    def _consume_token(self):
        # Redis token bucket; 10 tokens, refill 1 every 6 seconds.
        ...

    def _check_object_cap(self):
        # Cached `/account/usage/` snapshot — refuse calls past HARD_PCT.
        ...
```

Three things this client does that the SofaScore one didn't:

1. **Cursor pagination as a generator** — no caller has to know about `nextCursor`.
2. **Token-bucket throttle** — the per-minute rate limit is hard, so we enforce it client-side.
3. **Object-cap pre-check** — refuses to make a call that would breach the 95% line.

---

## 3. Model changes

**Migration strategy:** dev DB wipe is the precedent ([sofa refactor-plan §5](../sofa/refactor-plan.md)). Same here. Three migrations: `Sport` rewrite (string PK), new `League` table, `Event` and `Team` PK type change. Production isn't running this stack yet (per the audit — mock client points at localhost), so no backfill required.

### 3.1 `Sport` — string PK, drop the SofaScore numeric ID

| Field | Type | Source |
|---|---|---|
| `id` | CharField(32), **PK** | SGO `sportID` (`BASEBALL`, `BASKETBALL`, `FOOTBALL`, `HOCKEY`, `SOCCER`) |
| `name` | CharField(64) | SGO `sport.name` |
| `active` | Boolean | derived: `active = any(league.active for league in self.leagues.all())` — kept as cached column, updated by signal on `League.active` change |
| `created` / `updated` | auto | |

`slug` is dropped; the ID itself is the slug.

### 3.2 `League` — new model

This is the new center of gravity. Allowlist toggles live here.

| Field | Type | Source / Notes |
|---|---|---|
| `id` | CharField(48), **PK** | SGO `leagueID` (`NFL`, `NBA`, `NCAAB`, `NCAAF`, `NHL`, `MLB`, `MLS`, `UEFA_CHAMPIONS_LEAGUE`, …) |
| `sport` | FK → `Sport` | SGO `league.sportID` |
| `name` | CharField(128) | SGO `league.name` |
| `short_name` | CharField(48) | SGO `league.shortName` if available |
| `active` | Boolean, default False | toggle in admin / fixtures. **The sole allowlist.** |
| `refresh_cadence_minutes` | PositiveIntegerField, default 720 | per-league cron tuning (see §1). |
| `last_refreshed_at` | DateTimeField, nullable | last successful events-ingest finish. |
| `created` / `updated` | auto | |

Initial fixture: 8 rows, all `active=True`, with `refresh_cadence_minutes` per the table in §1.

### 3.3 `Event` — string PK, FK to League

The shape stays mostly the same; only PKs and a couple of fields move.

| Field | Type | Source / Notes |
|---|---|---|
| `id` | CharField(32), **PK** | SGO `eventID` |
| `public_id` | UUIDField, auto | unchanged — URL stability |
| `sport` | FK → `Sport` | denormalized for index; `event.league.sport_id` is the source of truth |
| `league` | FK → `League` | SGO `leagueID` |
| `type` | CharField(16) | SGO `type` (`match`) |
| `season_label` | CharField(64) | SGO `info.seasonWeek` |
| `start_time` | DateTimeField, indexed | SGO `status.startsAt` |
| `previous_starts_at` | JSONField, default list | SGO `status.previousStartsAt` (history of reschedules) |
| `status_type` | CharField(32), indexed | derived (see §3.5) |
| `status_display` | CharField(64) | SGO `status.displayLong` |
| `current_period_id` | CharField(16), nullable | SGO `status.currentPeriodID` |
| `is_live` | Boolean, indexed | SGO `status.live` |
| `is_finalized` | Boolean | SGO `status.finalized` |
| `completed` | Boolean | derived (`ended && finalized`) — kept for legacy readers |
| `home_team` / `away_team` | FK → `Team` | resolved from embedded `teams.home/.away` |
| `home_score` / `away_score` | IntegerField, nullable | derived from `points` odds (see [settlement-plan.md §2.1](settlement-plan.md)) |
| `winner` | CharField(255), nullable | derived |
| `winner_code` | SmallIntegerField, nullable | 1=home, 2=away, 3=draw |
| `feed_locked` | Boolean | SGO `status.cancelled` (renamed for clarity later) |
| `last_provider_refresh_at` | DateTimeField, nullable | bookkeeping for cadence checks |
| `raw_payload` | JSONField, default dict | optional — last raw event body, for debugging. `Meta.dump_object` to keep migrations cheap. |

Drop: `tournament_id`, `tournament_name`, `tournament_slug`, `unique_tournament_id`, `category_id`, `category_name`, `season_id`, `season_name`, `round_number`. SGO doesn't have these concepts; `League` carries the analogue.

### 3.4 `Team` — composite PK `(league, teamID)`

SGO defines teams **per league** — `ARSENAL_EPL` ≠ `ARSENAL_UEFA_CHAMPIONS_LEAGUE`. We make that explicit in our schema so we never accidentally collapse the same physical club across leagues.

**PK design:** synthesized string `f"{league_id}:{team_id}"` (e.g. `EPL:ARSENAL_EPL`), with a `unique_together` on `(league, team_id)`. Keeps FK columns simple (single string) while encoding the composite identity.

| Field | Type | Source / Notes |
|---|---|---|
| `id` | CharField(80), **PK** | synthesized: `f"{league.id}:{payload['teamID']}"` |
| `public_id` | UUIDField, auto | unchanged |
| `league` | FK → `League` | the league context |
| `team_id` | CharField(48) | raw SGO `teamID`. Combined with `league` is unique. |
| `sport` | FK → `Sport` | denorm for filtering |
| `name_long` | CharField(128) | `names.long` |
| `name_medium` | CharField(64) | `names.medium` |
| `name_short` | CharField(32) | `names.short` |
| `primary_color` | CharField(9), nullable | `colors.primary` |
| `secondary_color` | CharField(9), nullable | `colors.secondary` |
| `primary_contrast` | CharField(9), nullable | `colors.primaryContrast` |
| `secondary_contrast` | CharField(9), nullable | `colors.secondaryContrast` |
| `stat_entity_id` | CharField(8) | `home` or `away` (their position-in-event marker) |
| `logo_url` | ImageField, nullable | always null in v1 — SGO doesn't ship logos. |
| `created` / `updated` | auto | |

```python
class Team(AbstractModel):
    id = models.CharField(max_length=80, primary_key=True)
    league = models.ForeignKey(League, on_delete=models.PROTECT, related_name="teams")
    team_id = models.CharField(max_length=48)
    # ... other fields ...

    class Meta:
        unique_together = [("league", "team_id")]
        indexes = [models.Index(fields=["league", "team_id"])]
```

Drop: `slug`, `national`, `gender`, `name_code`, `country_*`, `user_count`. None of those exist in SGO.

`Team.objects.upsert_from_payload(team_dict, league_obj)`:
```python
def upsert_from_payload(self, payload: dict, league: "League") -> "Team":
    pk = f"{league.id}:{payload['teamID']}"
    return self.update_or_create(
        id=pk,
        defaults=dict(league=league, team_id=payload["teamID"],
                      sport=league.sport, **_extract_names_and_colors(payload)),
    )[0]
```

Implication for `Event.home_team` / `Event.away_team`: the FK column type stays `CharField(80)` since it points at the synthesized PK. Both teams in the same event always share `league`, so no cross-league joining surprises.

---

### 3.5 `Bookmaker` — new model

We persist SGO's `byBookmaker` payload so the front end can render per-book prices and deeplinks.

| Field | Type | Source |
|---|---|---|
| `id` | CharField(32), **PK** | SGO bookmakerID (`draftkings`, `fanduel`, `betmgm`, …) |
| `name` | CharField(64) | display name |
| `active` | Boolean, default True | toggle (e.g. retired books) |
| `created` / `updated` | auto | |

Seeded from `links.bookmakers` keys observed in the first ingest pass; `update_or_create` on every event ingest (cheap, idempotent). On Amateur tier we see ≤9 bookmakers, so the table stays tiny.

---

### 3.6 `BookmakerSelection` — per-book quote rows

One row per `(Selection, Bookmaker)` pair. **Current quote only**, no time-series — that's `OddsQuote`'s job for the consensus (fair) line. If we want per-book movement history later, mirror the same shape into a `BookmakerOddsQuote` table.

| Field | Type | Source |
|---|---|---|
| `selection` | FK → `Selection`, on_delete=CASCADE | |
| `bookmaker` | FK → `Bookmaker`, on_delete=PROTECT | |
| `decimal_odds` | DecimalField(8,4), nullable | American → decimal converted from `byBookmaker.{book}.odds` |
| `spread` | DecimalField(6,2), nullable | `byBookmaker.{book}.spread` |
| `over_under` | DecimalField(6,2), nullable | `byBookmaker.{book}.overUnder` |
| `available` | Boolean | `byBookmaker.{book}.available` |
| `deeplink` | URLField, blank | `byBookmaker.{book}.deeplink` |
| `last_updated_at` | DateTimeField | `byBookmaker.{book}.lastUpdatedAt` |
| `created` / `updated` | auto | |

```python
class BookmakerSelection(models.Model):
    selection = models.ForeignKey("event.Selection", on_delete=models.CASCADE,
                                  related_name="by_book")
    bookmaker = models.ForeignKey("event.Bookmaker", on_delete=models.PROTECT)
    decimal_odds = models.DecimalField(max_digits=8, decimal_places=4, null=True)
    spread = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    over_under = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    available = models.BooleanField(default=True)
    deeplink = models.URLField(blank=True)
    last_updated_at = models.DateTimeField()
    # ...
    class Meta:
        unique_together = [("selection", "bookmaker")]
        indexes = [
            models.Index(fields=["selection", "available"]),
            models.Index(fields=["bookmaker", "available"]),
        ]
```

**Settlement does NOT read this table.** The settlement engine grades off `Selection.decimal_odds` (the fair-odds consensus) and SGO's per-odd `score` ([settlement-plan.md §2](settlement-plan.md)). Per-book rows are display-only.

`Selection`-detail REST responses gain a `byBookmaker: [{...}]` array sourced from this table.

### 3.5 Status mapping (the single most-touched rule)

```python
def derive_status_type(status: dict) -> str:
    if status.get("cancelled"): return "canceled"
    if status.get("finalized") and status.get("ended"): return "finished"
    if status.get("live"): return "inprogress"
    if status.get("delayed"): return "postponed"
    return "notstarted"
```

- `delayed` is SGO's word for what we call `postponed`. Fine — same downstream effect (settlement engine voids past-window).
- `finalized` is the green light to settle (see [settlement-plan.md](settlement-plan.md)). `ended` alone is not enough; SGO marks `ended=true` the moment regulation finishes, but `finalized=true` only after grading is locked. Wait for both.

---

## 4. Cron refactor

### 4.1 Replace single 12-hour `event_cron` with per-league cadence

```python
# core/event/crons/eventUpdate.py

class EventCron:
    def __init__(self):
        self.client = SportsGameOddsClient()

    def update_due_leagues(self):
        now = timezone.now()
        for league in League.objects.filter(active=True).select_related("sport"):
            cadence = timedelta(minutes=league.refresh_cadence_minutes)
            if league.last_refreshed_at and (now - league.last_refreshed_at) < cadence:
                continue
            try:
                self.ingest_league(league)
            except RateLimitedError:
                logger.warning("Rate limited on %s, skipping tick", league.id)
                continue

    def ingest_league(self, league: League):
        starts_after  = timezone.now() - timedelta(hours=2)
        starts_before = timezone.now() + timedelta(hours=72)
        count = 0
        for ev in self.client.get_events(
            league_id=league.id,
            starts_after=starts_after.isoformat(),
            starts_before=starts_before.isoformat(),
            include_open_close=True,
        ):
            self._upsert(ev, league)
            count += 1
        league.last_refreshed_at = timezone.now()
        league.save(update_fields=["last_refreshed_at"])
        logger.info("Ingested %d events for %s", count, league.id)

    def _upsert(self, payload: dict, league: League):
        home = Team.objects.upsert_from_payload(payload["teams"]["home"], league)
        away = Team.objects.upsert_from_payload(payload["teams"]["away"], league)
        event = Event.objects.upsert_from_payload(payload, league=league, home=home, away=away)
        # Odds are embedded; ingest_odds reuses the existing normalize layer.
        from core.event.odds.normalize import ingest_odds_sgo
        ingest_odds_sgo(event, payload.get("odds") or {})
        return event
```

### 4.2 Beat schedule

```python
CELERY_BEAT_SCHEDULE = {
    "event_cron": {
        "task": "core.crons.tasks.event_cron",     # calls update_due_leagues
        "schedule": crontab(minute=15, hour="*/2"),  # every 2h, gives the per-league cadence room to skip
    },
    "warm_upcoming_odds_cron": {
        "task": "core.crons.tasks.warm_upcoming_odds_cron",
        "schedule": crontab(minute="*/30"),
    },
    "settle_pending_cron": {
        "task": "core.crons.tasks.settle_pending_cron",
        "schedule": crontab(hour=3, minute=30),
    },
    "complete_matches_cron": {
        "task": "core.crons.tasks.complete_matches_cron",
        "schedule": crontab(hour=0, minute=0),
    },
}
```

The outer beat ticks every 2h; per-league `refresh_cadence_minutes` determines whether each league actually fetches. Net effect:
- NBA / live-heavy leagues fetch every 6h.
- NFL / MLB / NHL / MLS fetch every 12h.
- NCAAB / NCAAF / UCL fetch every 24h (typically only on game day).

`warm_upcoming_odds_cron` becomes much simpler — it walks events starting in the next 6h and refreshes each via `client.get_event(eventID)`. Same cadence (30min) works.

### 4.3 Live mode (separate, cheap)

For events with `is_live=True`, a tighter cron:
```python
"live_events_cron": {
    "task": "core.crons.tasks.live_events_cron",
    "schedule": crontab(minute="*/2"),  # every 2 min during live windows
}
```

Implementation skips itself when no `Event.is_live=True` row exists. When it runs:
```
GET /v2/events?leagueID={league}&live=true&includeOpenCloseOdds=false
```
Per-league, but typically only 0–4 live events at a time → ~10 objects/tick max. Bounded.

---

## 5. Migration & rollout order

1. **New env var** `SPORTSGAMEODDS_API_KEY`. Get a free key from sportsgameodds.com.
2. **Add the client** [core/event/sportsgameodds.py](../../core/event/sportsgameodds.py) (no callers yet).
3. **New `League` model + migration**, plus `seed_sports_leagues` management command that calls `/sports/` and `/leagues/` once and populates the table. Run manually.
4. **Adjust fixture / admin** so the 8 free-tier leagues default to `active=True`.
5. **Sport / Event / Team PK migration** — string PKs. **Dev DB wipes here**; prod isn't on this stack.
6. **Add the SGO normalizer entry point** `ingest_odds_sgo` (sibling to existing `ingest_odds`), keep the sofa one for the rollback window. See [odds-system-plan.md §5](odds-system-plan.md).
7. **Rewire `EventCron`** to use the SGO client + new model layout.
8. **Beat schedule swap** — point `event_cron` at the new task name; remove SofaScore-only crons (none today; the live-events fallback in [eventUpdate.py](../../core/event/crons/eventUpdate.py) goes away).
9. **Smoke test** — `python manage.py shell -c "EventCron().ingest_league(League.objects.get(id='NFL'))"` against a real key. Verify Event rows land, odds populate, settlement-status enums are still working.
10. **Delete sofa client + taxonomy + normalize** in a follow-up commit once SGO is running cleanly for one full week.

Each step is independently shippable. Steps 1–4 are reversible without touching the existing pipeline; step 5 is the breaking one.

---

## 6. Decisions — locked

| # | Decision | Resolution |
|---|---|---|
| 1 | Per-league `refresh_cadence_minutes` | NFL/MLB/NHL/MLS = 720; NBA = 360; NCAAB/NCAAF/UCL = 1440. Revisit after week 1 of usage telemetry. |
| 2 | `byBookmaker` storage | **Keep.** New `Bookmaker` + `BookmakerSelection` models (§3.5, §3.6). Fair-odds consensus on `Selection` is canonical for settlement; per-book is display-only. |
| 3 | Player props on day 1 | **No.** PROPS_PLAYER stays out. Lift the `statEntityID in (home, away, all)` filter when we want to enable it. |
| 4 | Team logos | **Null in v1.** Field stays for later hotlinking. |
| 5 | `Team` PK shape | **Composite `(league, team_id)` synthesized into a single CharField PK** (§3.4). |
| 6 | Object-cap behavior at 95% | **Deferred.** Default fail-closed for cron, fail-open for user-detail (so a runaway cron can't blow the budget but UI never shows blank). Revisit alongside the future aggregator (§7). |
| 7 | Keep SofaScore client as fallback | **No.** Cut over cleanly. Maintaining a parallel client + normalizer + settlement path doubles the migration surface for no rollback benefit (prod isn't on this stack yet). |

---

## 7. Future provider boundary (aggregator note)

The user is considering a dedicated **data-aggregator service** later — a separate process that talks to SportsGameOdds (and potentially other providers) and exposes a private internal API to this Django app. When that lands, the Django app stops being the rate-limited consumer; the aggregator absorbs the 10/min and 2.5k/mo caps.

To make that swap a one-file change later (without retrofitting now), the SGO client lives behind a thin factory:

```python
# core/event/providers/__init__.py
from django.conf import settings
from .sportsgameodds import SportsGameOddsClient

def get_events_client():
    """Returns the configured events provider client.

    Today: SportsGameOdds direct.
    Future: replace dispatch to return AggregatorClient when EVENTS_PROVIDER='aggregator'.
    """
    return SportsGameOddsClient()
```

All ingest code calls `get_events_client()` instead of `SportsGameOddsClient()` directly. When the aggregator ships:
- Add `core/event/providers/aggregator.py` exposing the same surface (`get_events`, `get_event`, `get_account_usage`).
- Flip `get_events_client()` to dispatch on a settings flag.
- The cron, normalizer, and settlement layers don't change at all — they consume normalized dicts, not provider-shaped responses.

That's the only "future-proofing" we do now. **No abstract base class, no full provider-protocol interface**: one factory function and a discipline of importing through it. If the aggregator never ships, this costs nothing.

Decisions #6 (cap behavior) and #2 (byBookmaker) become aggregator concerns later: the aggregator can manage caps centrally and pre-flatten `byBookmaker` if it wants to. Today both stay on this side of the line.

---

## 8. Decisions still open (need a real API key — see [odds-system-plan.md §9](odds-system-plan.md))

These don't block the architecture but should be answered before the cutover commit. They map directly to one-`curl` probes against a free SGO key. Want a probe script? See the offer at the end of this conversation — it'll write a `probes.sh` that runs all six in sequence and dumps the relevant fields.

The questions deferred to the probes:
- Does `score` ship on every odd post-finalization, or only some?
- MLS/UCL `ml3way` — keyed on `periodID="reg"` or `"game"`?
- Does NCAAB ship `5min` / `10min` periods?
- Does the response count player-prop odds as separate objects?
- Does `includeAltLines=true` blow up the response size?
- Player-prop oddID shape — does the playerID token contain dashes?
