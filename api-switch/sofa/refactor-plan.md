# Refactor Plan — Events & Teams on SofaScore API

**Hard constraint: 500 API calls / month.** Everything below is designed around that budget. Source of truth for the new API: [/Users/joem/dev/sports-scores/api/sofascore.py](../../sports-scores/api/sofascore.py) and the sample responses in `/Users/joem/dev/sports-scores/json/`.

---

## Budget math

500 calls/month ≈ **16.6 calls/day** ≈ **0.69 calls/hour**.

Things that cost a call:
- `/sports/list` — once. Trivial.
- `/tournaments/get-scheduled-events?categoryId={sport_id}` — **one per sport per tick**. This is the entire event cron.
- `/matches/get-all-odds?matchId={id}` — per match. **Not in any cron.** On-demand only (when a user opens a match). Budget the remainder for this.
- `/tournaments/get-live-events?sport={slug}` — per sport per tick. Not in the initial cron.

Things that cost **zero** calls:
- Creating/updating a Team. Teams are fully embedded in the event response — we extract them from `homeTeam` / `awayTeam` and upsert. **This is the whole point of the migration.**
- Deriving scores, winners, tournaments, categories, seasons — all embedded in the event response.

### Cron cadence — pick one

Let `S` = sports in our allowlist, `T` = ticks/day. Monthly cost ≈ `S × T × 30`.

| Option | Sports | Ticks/day | Interval | Calls/month | Remaining for odds |
|---|---|---|---|---|---|
| **A — lean** | 3 (e.g. football, basketball, american football) | 2 | every 12h | 180 | 320 |
| **B — balanced** | 5 | 2 | every 12h | 300 | 200 |
| **C — fresher** | 3 | 4 | every 6h | 360 | 140 |
| **D — max coverage** | 5 | 3 | every 8h | 450 | 50 |

Recommended: **Option A or B.** Leaves real headroom for on-demand odds fetches (those will dominate once users place bets) and for ad-hoc manual runs / debugging.

**`sport_cron` is removed from Celery Beat.** `/sports/list` runs as a one-shot seed (manual `manage.py` command or a migration data fixture). The 26 SofaScore sports barely ever change; polling them daily is 30 wasted calls.

**Safety valve — a monthly counter.** Add a Redis counter `sofascore:calls:{YYYY-MM}` that every request bumps. The client refuses calls when it hits, say, 480, and logs loudly. One cheap wrapper, catches misbehaving crons and runaway loops.

---

## Event retention — keep everything

**We do not delete old events.** The existing `event_delete_outdated_cron` / `DeleteEventCron.delete_outdated_events` is removed from the schedule and the code path. Historical events stay in the DB for analytics, replay, and any future bet-settlement needs.

Practical implication for UI: any view that previously relied on "there are no outdated events" needs to filter by `status_type` / `start_time` explicitly instead of assuming the cron already cleaned them out. In practice that means lists should filter `status_type__in=["notstarted", "inprogress"]` (or similar) rather than fetching all rows.

---

## Guiding principles

1. **One API, one host.** Everything goes through `sofascore.p.rapidapi.com`. Drop `odds.p.rapidapi.com`.
2. **Teams are a by-product of events.** Never call a team endpoint in any cron. Logos stay null for now; fetched lazily when a user actually views a team detail page, not on ingest.
3. **No odds in the cron, period.** Odds fetching is user-triggered. A separate plan handles that model rewrite.
4. **Store provider IDs, don't invent them.** SofaScore uses stable integer IDs for sports, teams, events, tournaments. Make them our PKs where possible.
5. **Every outbound call goes through one client** (`core.event.sofascore.SofaScoreClient`) that increments the monthly counter. One place to rate-limit, log, and test.
6. **Events are append-only.** Upsert on provider id. Never delete.

---

## Endpoints used by this plan

### `/sports/list?countryCode=` — one-time seed
Populates `Sport`. Runs from `manage.py seed_sports` or a data migration. Zero recurring cost.

### `/tournaments/get-scheduled-events?categoryId={sport_id}` — the only recurring call
Returns `{ "events": [...] }`. One call per sport per tick. Each event contains complete `homeTeam` and `awayTeam` objects, the tournament, category, season, scores, and status — everything needed to upsert events **and** teams in one network hit.

Trimmed shape we care about:
```json
{
  "id": 14024001,
  "slug": "chelsea-brighton-and-hove-albion",
  "customId": "FsN",
  "startTimestamp": 1776798000,
  "status": { "code": 100, "description": "Ended", "type": "finished" },
  "winnerCode": 1,
  "tournament": {
    "id": 1, "name": "Premier League", "slug": "premier-league",
    "uniqueTournament": { "id": 17, "name": "Premier League" },
    "category": {
      "id": 1, "name": "England",
      "sport":   { "id": 1, "slug": "football", "name": "Football" },
      "country": { "alpha2": "EN", "alpha3": "ENG", "name": "England" }
    }
  },
  "season": { "id": 76986, "name": "Premier League 25/26", "year": "25/26" },
  "homeTeam": { "id": 30, "name": "Brighton & Hove Albion", "nameCode": "BHA", ... },
  "awayTeam": { "id": 38, "name": "Chelsea", "nameCode": "CHE", ... },
  "homeScore": { "current": 3, "period1": 1, "period2": 2, "normaltime": 3 },
  "awayScore": { "current": 0, "period1": 0, "period2": 0, "normaltime": 0 }
}
```

### Out of scope (explicitly)
- `/tournaments/get-live-events` — future live-score cron. Would be costly (`S × 30` per month per tick).
- `/matches/detail` — only if a detail page needs more than what the list returns.
- `/matches/get-all-odds` — on-demand, separate plan.

---

## Model changes

### `Sport` — [core/event/models/sport.py](../core/event/models/sport.py)

Old PK `key` is actually a league id (`americanfootball_nfl`). SofaScore treats sports as a low-cardinality category (26 entries).

| Field | Type | Source |
|---|---|---|
| `id` | IntegerField **PK** | `sport.id` |
| `slug` | CharField(64), unique | `sport.slug` |
| `name` | CharField(128) | `sport.name` |
| `active` | Boolean, default `True` | allowlist toggle |
| `created` / `updated` | auto | |

Drop: `group`, `description`, `has_outrights`. Nothing consumes them in a way that blocks removal.

Seed once from `/sports/list` (manual command). No recurring cost.

---

### `Team` — [core/event/models/team.py](../core/event/models/team.py)

Upserted purely from the embedded `homeTeam` / `awayTeam` objects in event responses. **Zero API calls.**

| Field | Type | Source | Notes |
|---|---|---|---|
| `id` | IntegerField **PK** | `team.id` | SofaScore id |
| `public_id` | UUIDField, auto | — | keep for URL stability |
| `name` | CharField(255) | `team.name` | |
| `slug` | CharField(255), indexed | `team.slug` | |
| `short_name` | CharField(64) | `team.shortName` | |
| `name_code` | CharField(8) | `team.nameCode` | `BHA`, `CHE` |
| `gender` | CharField(4) | `team.gender` | |
| `national` | Boolean | `team.national` | |
| `sport` | FK → `Sport` | `team.sport.id` | |
| `country_name` | CharField(128), nullable | `team.country.name` | |
| `country_alpha2` | CharField(4), nullable | `team.country.alpha2` | |
| `country_alpha3` | CharField(4), nullable | `team.country.alpha3` | |
| `primary_color` | CharField(9), nullable | `team.teamColors.primary` | |
| `secondary_color` | CharField(9), nullable | `team.teamColors.secondary` | |
| `text_color` | CharField(9), nullable | `team.teamColors.text` | |
| `logo_url` | ImageField, nullable | — | **left null.** Filled lazily on first detail view, if ever. |
| `user_count` | IntegerField, default 0 | `team.userCount` | cheap popularity signal |
| `created` / `updated` | auto | | |

Drop: `title`, `group`, `team_id` (replaced by PK), `country_code` (split into alpha2/alpha3), unique-on-`team_name` (collides across countries).

Manager gains: `Team.objects.upsert_from_payload(team_dict, sport_obj)` — idempotent, called by the event cron for every event's home and away team. No network.

Drop from manager: `get_object_by_team_name`, `get_object_by_team_id`, `create_team` — subsumed.

**Delete `TeamCron` entirely.** Its file can go away once callers are rewired to `Team.objects.upsert_from_payload`.

---

### `Event` — [core/event/models/event.py](../core/event/models/event.py)

| Field | Type | Source | Notes |
|---|---|---|---|
| `id` | BigIntegerField **PK** | `event.id` | SofaScore ids climb into the 10Ms |
| `public_id` | UUIDField, auto | — | URL stability |
| `slug` | CharField(255) | `event.slug` | |
| `custom_id` | CharField(16), nullable | `event.customId` | |
| `sport` | FK → `Sport` | `event.tournament.category.sport.id` | |
| `tournament_id` | IntegerField, nullable, indexed | `event.tournament.id` | denormalized for now |
| `tournament_name` | CharField(255) | `event.tournament.name` | |
| `tournament_slug` | CharField(255) | `event.tournament.slug` | |
| `unique_tournament_id` | IntegerField, nullable | `event.tournament.uniqueTournament.id` | |
| `category_id` | IntegerField, nullable | `event.tournament.category.id` | country/region |
| `category_name` | CharField(128), nullable | `event.tournament.category.name` | |
| `season_id` | IntegerField, nullable | `event.season.id` | |
| `season_name` | CharField(128), nullable | `event.season.name` | |
| `round_number` | IntegerField, nullable | `event.roundInfo.round` | |
| `start_time` | DateTimeField, indexed | `datetime.fromtimestamp(event.startTimestamp, tz=utc)` | real datetime, not a string |
| `status_code` | IntegerField | `event.status.code` | |
| `status_type` | CharField(32), indexed | `event.status.type` | `finished`, `inprogress`, `notstarted`, `postponed` |
| `status_description` | CharField(64) | `event.status.description` | |
| `completed` | Boolean, default False | `status.type == "finished"` | keeps legacy readers working |
| `home_team` | FK → `Team` | `event.homeTeam.id` | |
| `away_team` | FK → `Team` | `event.awayTeam.id` | |
| `home_score` | IntegerField, nullable | `event.homeScore.current` | |
| `away_score` | IntegerField, nullable | `event.awayScore.current` | |
| `scores_payload` | JSONField, default dict | full score blob | for detail views |
| `winner_code` | SmallIntegerField, nullable | `event.winnerCode` | 1=home, 2=away, 3=draw |
| `winner` | CharField(255), nullable | derived | keeps legacy readers working |
| `feed_locked` | Boolean | `event.feedLocked` | |
| `created` / `updated` | auto | | |

Drop: `sport_key`, `sport_title`, `title`, `group`, `description`, `commence_time` (string), `home_team` / `away_team` as CharFields (replaced by FKs, which take the clean name).

Renames: `home_team_team` → `home_team`, `away_team_team` → `away_team`.

Derived fields (on save or in an upsert manager method):
```python
status_type = payload["status"]["type"]
completed = (status_type == "finished")
wc = payload.get("winnerCode")
winner = (
    home_team.name if wc == 1 else
    away_team.name if wc == 2 else
    "Draw"          if wc == 3 else
    None
)
```

---

## Cron refactor

### Delete
- `TeamCron.get_team_api`, `get_logo`, `check_team` in [core/event/crons/teamUpdate.py](../core/event/crons/teamUpdate.py). Whole file can go if no model helpers remain.
- `EventCron.get_sport_odds`, the old `get_sport_events` body, `get_upcoming_odds` in [core/event/crons/eventUpdate.py](../core/event/crons/eventUpdate.py).
- `sport_cron` from `CELERY_BEAT_SCHEDULE` in [CoreRoot/settings.py](../CoreRoot/settings.py).
- `event_delete_outdated_cron` from `CELERY_BEAT_SCHEDULE`. We keep historical events.
- `DeleteEventCron` class in [core/event/crons/deleteEvents.py](../core/event/crons/deleteEvents.py). File can go.
- The `good_leagues` / `broken_leagues` lists — no longer meaningful (those were Odds API league keys). Replaced by `Sport.active`.

### Add: `core/event/sofascore.py`
Single thin HTTP client. Mirrors [/Users/joem/dev/sports-scores/api/sofascore.py](../../sports-scores/api/sofascore.py), with two changes:
- Reads key from `os.getenv("RAPID_API_KEY")`.
- Wraps every request in the monthly counter (`incr` on Redis, fail closed at the cap).

### Rewrite: `EventCron.ingest_sport(sport)`
```python
def ingest_sport(self, sport: Sport):
    payload = self.client.get_scheduled_sport_events(sport.id)  # 1 API call
    for ev in payload.get("events", []):
        home = Team.objects.upsert_from_payload(ev["homeTeam"], sport)  # 0 calls
        away = Team.objects.upsert_from_payload(ev["awayTeam"], sport)  # 0 calls
        Event.objects.upsert_from_payload(ev, sport=sport, home=home, away=away)  # 0 calls
```

And `update_all_events` iterates only over the allowlisted sports:
```python
def update_all_events(self):
    for sport in Sport.objects.filter(active=True):
        self.ingest_sport(sport)
```

The allowlist is now data, not code — toggle `Sport.active` in the admin. No more hard-coded league lists.

### Beat schedule (new)
```python
CELERY_BEAT_SCHEDULE = {
    "event_cron": {
        "task": "core.crons.tasks.event_cron",
        "schedule": crontab(hour="*/12", minute=0),   # Option A/B default
    },
}
```

`sport_cron` and `event_delete_outdated_cron` removed. Adjust interval to match the option we pick.

---

## Migration & rollout order

1. Add `core/event/sofascore.py` client + the monthly Redis counter wrapper.
2. Add `core.event.commands.seed_sports` (or a data migration) that populates `Sport` from `/sports/list`. One call.
3. New model migration — rewrite `Sport`, `Team`, `Event` per above. Dev DB gets wiped; acceptable.
4. Rewrite `Team.objects.upsert_from_payload` and `Event.objects.upsert_from_payload`.
5. Rewrite `EventCron.ingest_sport` + `update_all_events`.
6. Run `seed_sports` manually once. Flip `active=True` on the 3–5 sports we want.
7. Run `ingest_sport(football)` manually. Verify Teams and Events populate without a team API call.
8. Wire into Celery Beat with the chosen cadence.
9. Delete old code (TeamCron, old EventCron methods, DeleteEventCron, removed beat entries).
10. Grep consumers (`core/event/views/`, `core/game/`, `core/match/`, `core/portal/`, templates) for old field names (`sport_key`, `sport_title`, `commence_time`, `home_team_team`, `away_team_team`, `team_name`) and update.

---

## Decisions needed before coding

1. **Cron option — A / B / C / D?** (affects cadence + allowlist size)
2. **Allowlist — which sports?** Default guess: football (1), basketball (2), american football (63), baseball (64), ice hockey (4). Pick any subset matching the option above.
3. **Monthly counter — OK to add the Redis guard?** Costs ~nothing; catches future mistakes before they blow the quota.
4. **Field renames (`home_team_team` → `home_team`) — OK to break any downstream templates/serializers in the same pass?** Grep should be quick.
5. **Dev wipe vs prod data.** Dev is fine. If prod has real data, we script a one-off backfill that walks existing `team_id` values.

Answer those five and this becomes mechanical to implement.
