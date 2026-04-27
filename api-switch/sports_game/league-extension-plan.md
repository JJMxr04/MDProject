# League / Sport Extension Plan

**Goal:** describe how a new league (e.g., EPL when we upgrade tiers) or a brand-new sport (e.g., UFC) gets added **without touching the ingest, normalization, or settlement code**. Replaces the sofa-era [hockey-extension-plan.md](../sofa/hockey-extension-plan.md) — the SGO design generalizes that work.

**Builds on:** [refactor-plan.md](refactor-plan.md), [odds-system-plan.md](odds-system-plan.md).

**Tier today:** Amateur. 8 leagues, 5 sports. The 8 are seeded `active=True`; the architecture supports flipping any other SGO league live with a single admin toggle, no code change.

---

## 1. The principle: data-driven, not code-driven

The sofa hockey extension required ~30 lines of new taxonomy entries, 5 lines of `SCOPE_MAP` additions, classifier rules for hockey-specific choice names, and a one-off code branch (`LIVE_ONLY_FALLBACK`) for the empty-scheduled-events bug. Net: a small but real code change every time a sport got added.

SGO's structured `oddID` lets us flip that. Adding a league requires:

1. **A row in `League`** (admin form or fixture).
2. **(Sometimes) a row in `Sport`** if the parent sport is also new.
3. **(Sometimes) a `TYPE_OVERRIDES` entry** in [sgo_taxonomy.py](#3-when-code-changes-are-required) for sport-specific market naming (BTTS, puck line). One-line addition, no migration.

That's it. The normalizer, settlement engine, REST API, taxonomy decomposer, and Celery beat work unchanged.

---

## 2. Adding a league — runbook

### Step 1 — confirm SGO supports it

```
curl -H "X-Api-Key: $SPORTSGAMEODDS_API_KEY" \
     'https://api.sportsgameodds.com/v2/leagues/'
```

Find the row. Note the exact `leagueID` (e.g., `EPL`, `LA_LIGA`, `BUNDESLIGA`). The parent `sportID` is in the same row.

### Step 2 — verify our tier covers it

Hit `/account/usage/` or check the pricing page; if our tier doesn't include this league, the call returns 403. Don't proceed.

### Step 3 — insert the rows

Two approaches:
- **Admin UI:** create a `League` with `id=<leagueID>`, `sport=<existing or new Sport>`, `name=…`, `short_name=…`, `active=True`, `refresh_cadence_minutes=720`.
- **Data migration / fixture:** preferred for repeatability:

```python
# core/event/migrations/000X_seed_epl.py
def forwards(apps, schema_editor):
    Sport = apps.get_model("event", "Sport")
    League = apps.get_model("event", "League")
    soccer, _ = Sport.objects.get_or_create(id="SOCCER", defaults={"name": "Soccer"})
    League.objects.update_or_create(
        id="EPL",
        defaults=dict(sport=soccer, name="English Premier League",
                      short_name="EPL", active=True, refresh_cadence_minutes=720),
    )
```

### Step 4 — pick a cadence

Start with the default (720 min = 12h). Tune based on observed event volume per the [refactor-plan §1 budget table](refactor-plan.md). Heuristics:

| League event-density | Cadence |
|---|---|
| 5+ games/day in season (NBA, MLB, NHL, EPL) | 720 (12h) — drop to 360 if budget allows |
| 1–4 games/day in season (NFL, MLS) | 720 (12h) |
| Game-day only (NCAAB, NCAAF, UCL) | 1440 (24h), or live-events-cron only |
| Frequent live events (basketball during playoffs) | unchanged scheduled cadence + live-events-cron |

### Step 5 — first probe

Manual ingest:
```python
python manage.py shell -c "
from core.event.crons.eventUpdate import EventCron
from core.event.models.league import League
EventCron().ingest_league(League.objects.get(id='EPL'))
"
```

What to check in the result:
- Did `Event` rows land?
- Did `Team` rows land for both `home` and `away` (with `league=EPL`)?
- Did each event spawn `Market` rows for at least MONEYLINE / SPREAD / TOTAL?
- For finalized events in the window, did `Selection.settlement_status` land on WON / LOST?
- Any `unknown betTypeID` / `unknown periodID` warnings in logs?

If everything looks normal, leave `active=True`. If unknown betTypes / periods show up — that's where step 6 happens.

### Step 6 — record any sport-specific naming overrides

If the league introduces a market type whose auto-generated name collides or is ugly (e.g., `EPL_GOALS_YN_YES` instead of `EPL_BTTS`), add to `TYPE_OVERRIDES` (see [odds-system-plan.md §6.2](odds-system-plan.md)). One-line edit, ships in the next release.

### Step 7 — front-end exposure

The Flutter / REST front end already filters by `sportID` and `leagueID`. Adding a league flows through automatically — the `/api/events?league=EPL` query starts returning rows the moment ingest writes them.

---

## 3. When code changes _are_ required

The data-driven path covers ~95% of cases. These are the scenarios that still need code:

### 3.1 New `betTypeID`
SGO documents `ml`, `ml3way`, `sp`, `ou`, `yn`, `eo`. If they ship something new (e.g., `pl` for parlay leg, `if` for in-fight bets), `BET_TYPE_TO_CATEGORY` needs the new key. **One line in [sgo_taxonomy.py](../../core/event/odds/sgo_taxonomy.py).** No migration; the row joins MarketCategory enum values that already exist.

### 3.2 New `periodID`
For exotic period types (e.g., `lap` for racing, `game1`/`game2` for tennis sets-of-games). Add to `PERIOD_TO_SCOPE`. If the new value doesn't fit any existing `MarketScope` enum, add an enum value (model migration). E.g., `MarketScope.ROUND` for boxing/UFC.

### 3.3 New `sideID`
SGO ships `home`, `away`, `draw`, `over`, `under`, `yes`, `no`, `even`, `odd`. If they add `void`, `forfeit`, etc., add `SIDE_TO_SELECTION` row + `SelectionType` enum value (model migration).

### 3.4 New sport
Adding `BOXING` or `UFC` brings new statIDs (`rounds`, `knockouts`) and new periods (`round_1`–`round_12`). Procedure:

1. Add `Sport` row (`id="BOXING"`, `name="Boxing"`).
2. Add `League` rows under it (e.g., `id="BOXING_GENERAL"`).
3. Add new `MarketScope` enum values for unfamiliar periods (`ROUND_1`…`ROUND_12`); model migration.
4. Add `PERIOD_TO_SCOPE` rows pointing the new SGO `periodID` strings to the new scope values.
5. (Optional) `TYPE_OVERRIDES` for nicer market naming.

That's the full delta. Ingest, settlement, REST, and the Game/Match scoring layer **work without touching them** — they operate on `(category, scope, type, line, side)` regardless of sport.

### 3.5 Settlement for a never-before-seen stat
The settlement engine in [core/event/odds/settlement.py](../../core/event/odds/settlement.py) computes outcomes from `home_score` / `away_score` for moneyline/total/spread, and from per-odd `score` for everything else (see [settlement-plan.md §2](settlement-plan.md)).

When a new stat type lands (e.g., `corners` or `cards` in soccer), settlement still works automatically because:
- Per-odd `score` field is generic — settlement compares it to the odd's `bookOverUnder` / `closeOverUnder` regardless of stat name.
- For ML/SP, settlement still uses derived `home_score` / `away_score` (which we populate from the `points`/`goals`/`runs` odd's `score`).

**Settlement only needs new code when:**
- The "score" for a market isn't a single number (e.g., first-scorer is a team identity, not a count). Add a one-off settler in [settlement.py](../../core/event/odds/settlement.py) keyed on `Market.type`.
- A market settles on something other than its own `score` (rare).

---

## 4. Adding the next 9 leagues (Rookie tier)

The Rookie tier ($99/mo) bumps to 17 leagues / 100k objects. The 9 added are typically international soccer + a few specialty leagues. Concrete procedure when we upgrade:

1. Hit `/v2/leagues/` to dump the new league list.
2. Diff against current `League` rows.
3. Generate a data migration that `update_or_create`s each new row with `active=True`.
4. Tune cadences (most international soccer is matchday-only — start at 24h).
5. Bump `League.active` for the existing 8 to keep cadences as-is — quota's not the constraint anymore.
6. Update `SOFT_LIMIT` in the client (see [refactor-plan.md §2](refactor-plan.md)) — the object cap is now 100k.

No model migrations, no settlement changes, no normalizer changes (unless §3 conditions trigger — unlikely).

---

## 5. Removing a league

If we want to drop a league (tier downgrade, deprecated league):

1. Set `League.active=False` in admin.
2. The cron skips it next tick.
3. Existing `Event` / `Team` / `Market` rows stay (per the "events are append-only" principle from [sofa refactor-plan §40](../sofa/refactor-plan.md)). They go cold but don't break anything.
4. Optional cleanup: `python manage.py purge_inactive_leagues --since=180d` removes events older than 6 months for inactive leagues. Only do this once we have a real reason — disk is cheap.

---

## 6. Live-events-only fallback (no longer needed)

The sofa plan had a special case: SofaScore's scheduled-events endpoint sometimes returned empty for ice hockey, requiring a fallback to `/tournaments/get-live-events`. SGO's `/v2/events` accepts `live=true|false` as filters on the same endpoint, so:

- Scheduled fetch (default): no `live` filter, returns scheduled and live both.
- Live-only fetch (the new live cron): `live=true` filter.

There is no scenario where scheduled returns empty but live returns rows. The fallback class can be deleted.

---

## 7. Probes to run before flipping a league live

For a new league we've never tried, two cheap probes:

```bash
# 1. Pull one upcoming event — sanity check shape
curl -H "X-Api-Key: $SPORTSGAMEODDS_API_KEY" \
  "https://api.sportsgameodds.com/v2/events?leagueID=EPL&limit=1&oddsAvailable=true" | jq

# 2. Pull one finalized event — verify settlement signals
curl -H "X-Api-Key: $SPORTSGAMEODDS_API_KEY" \
  "https://api.sportsgameodds.com/v2/events?leagueID=EPL&finalized=true&limit=1" | jq
```

Look at:
- Are `oddID`s well-formed 5-tuples? Any with embedded dashes that break our splitter?
- Do `score` fields appear on each odd? On all odds, or only on a few?
- Does `status.finalized` line up with `status.ended`?
- What `periodID` values appear that we don't recognize?

If everything passes, set `active=True` and let the cron pick it up next tick.

---

## 8. Future additions to the architecture (deferred)

These aren't required for v1 but are simple extensions when we want them:

- **Player props.** Lift the `statEntityID in (home, away, all)` filter; add `Selection.subject_player_id`. Settlement reads the per-odd `score` field exactly as before.
- **Per-bookmaker movement history.** v1 stores only the *current* per-book quote in `BookmakerSelection`. A `BookmakerOddsQuote` table (mirror of `OddsQuote` but FK'd to `BookmakerSelection`) would track per-book line drift over time. Useful for closing-line-value analytics; not on the v1 roadmap.
- **Live in-play push (WebSockets).** SGO's All-Star tier ships WS — same fan-out idea as the sofa plan's deferred WS work.
- **Closing-line-value analytics.** SGO returns both opening and closing — `Selection.closing_decimal_odds` plus a daily aggregator.

None of these require schema rewrites; they're all additive.

---

**Bottom line:** new league → 1 fixture row + 1 cadence number. New sport → +1 row + a couple of enum entries. The architecture is league-data-driven, not league-hardcoded.
