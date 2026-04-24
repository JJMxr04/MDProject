# Old API Inventory — The Odds API + SofaScore

This document catalogs every external API call currently made for sports, events, odds, and teams. Use the **New API** section under each call to map the replacement SofaScore endpoint and what it returns. The **Django models** at the bottom are the shapes the new responses need to be transformed into.

---

## 1. Sports — List all sports/leagues

### Where it lives
- **File:** [core/event/crons/sportUpdate.py](../core/event/crons/sportUpdate.py)
- **Class/method:** `SportCron.get_sports()`
- **Called by:** `core.crons.tasks.sport_cron` (Celery beat, daily at midnight)

### Old API call
```
GET https://odds.p.rapidapi.com/v4/sports
Headers:
  X-RapidAPI-Key:  $RAPID_API_KEY
  X-RapidAPI-Host: odds.p.rapidapi.com
Query params:
  all=true
```

### Response shape (array of sports)
```json
[
  {
    "key": "americanfootball_nfl",
    "group": "American Football",
    "title": "NFL",
    "description": "US Football",
    "active": true,
    "has_outrights": false
  }
]
```

### Fields consumed
`key`, `group`, `title`, `description`, `active`, `has_outrights` — all persisted directly to the `Sport` model via `SportSerializer`.

### New API
- **Endpoint:** _TBD_
- **Query params:** _TBD_
- **Response shape:** _TBD_
- **Mapping notes:** _TBD_

---

## 2. Events — Scores / upcoming games per sport

### Where it lives
- **File:** [core/event/crons/eventUpdate.py](../core/event/crons/eventUpdate.py)
- **Class/method:** `EventCron.get_sport_events(sport)`
- **Called by:** `EventCron.update_all_events()` → `core.crons.tasks.event_cron` (every 4 hours)

### Old API call
```
GET https://odds.p.rapidapi.com/v4/sports/{sport_key}/scores
Headers:
  X-RapidAPI-Key:  $RAPID_API_KEY
  X-RapidAPI-Host: odds.p.rapidapi.com
Query params:
  daysFrom=3
```

### Response shape (array of events)
```json
[
  {
    "id": "e912304de2b2ce3030abf",
    "sport_key": "americanfootball_nfl",
    "sport_title": "NFL",
    "commence_time": "2026-04-25T20:00:00Z",
    "completed": false,
    "home_team": "Dallas Cowboys",
    "away_team": "New York Giants",
    "scores": [
      { "name": "Dallas Cowboys", "score": "21" },
      { "name": "New York Giants", "score": "14" }
    ]
  }
]
```

### Fields consumed
`id` (UUID), `sport_key`, `sport_title`, `commence_time`, `completed`, `home_team`, `away_team`, `scores` — written to `Event` model via `EventSerializer`.
Additionally, the code enriches the payload before save:
- `title`, `group`, `description` from the `Sport` row
- `home_team_team` / `away_team_team` from `TeamCron.check_team(...)` lookups

### New API
- **Endpoint:** _TBD_
- **Query params:** _TBD_
- **Response shape:** _TBD_
- **Mapping notes:** _TBD_

---

## 3. Odds — Per-sport betting lines

### Where it lives
- **File:** [core/event/crons/eventUpdate.py](../core/event/crons/eventUpdate.py)
- **Class/method:** `EventCron.get_sport_odds(sport)`
- **Called by:** `EventCron.update_all_events()` → `core.crons.tasks.event_cron` (every 4 hours)

### Old API call
```
GET https://odds.p.rapidapi.com/v4/sports/{sport_key}/odds
Headers:
  X-RapidAPI-Key:  $RAPID_API_KEY
  X-RapidAPI-Host: odds.p.rapidapi.com
Query params:
  daysFrom=3
  regions=us
  markets=h2h,spreads,totals
```

### Response shape (array of events with nested bookmakers → markets → outcomes)
```json
[
  {
    "id": "e912304de2b2ce3030abf",
    "sport_key": "americanfootball_nfl",
    "home_team": "Dallas Cowboys",
    "away_team": "New York Giants",
    "bookmakers": [
      {
        "id": "draftkings",
        "key": "draftkings",
        "title": "DraftKings",
        "last_update": "2026-04-22T15:00:00Z",
        "markets": [
          {
            "key": "h2h",
            "last_update": "2026-04-22T15:00:00Z",
            "outcomes": [
              { "name": "Dallas Cowboys",   "price": -150 },
              { "name": "New York Giants",  "price": +130 }
            ]
          },
          {
            "key": "spreads",
            "outcomes": [
              { "name": "Dallas Cowboys",   "price": -110, "point": -3.5 },
              { "name": "New York Giants",  "price": -110, "point": +3.5 }
            ]
          },
          {
            "key": "totals",
            "outcomes": [
              { "name": "Over",  "price": -110, "point": 47.5 },
              { "name": "Under", "price": -110, "point": 47.5 }
            ]
          }
        ]
      }
    ]
  }
]
```

### Fields consumed
- **Event:** `id` → used to `get_or_create(Event, id=...)`
- **Bookmaker:** `id`, `key`, `title`, `last_update`
- **Market:** `key`, `last_update`
- **Outcome:** `name` (≤ 50 chars), `price` (float), `point` (float, nullable)

### Market keys expected
`h2h` (moneyline), `spreads`, `totals`. Any new market keys from SofaScore can either be mapped to these three or the `Market.key` column can accept more values.

### New API
- **Endpoint:** _TBD_
- **Query params:** _TBD_
- **Response shape:** _TBD_
- **Mapping notes:** _TBD_

---

## 4. Upcoming Odds — Cross-sport upcoming events with odds (currently commented out)

### Where it lives
- **File:** [core/event/crons/eventUpdate.py](../core/event/crons/eventUpdate.py)
- **Class/method:** `EventCron.get_upcoming_odds()`
- **Called by:** (disabled — call is commented out in `update_all_events()`)

### Old API call
```
GET https://odds.p.rapidapi.com/v4/sports/upcoming/odds
Headers:
  X-RapidAPI-Key:  $RAPID_API_KEY
  X-RapidAPI-Host: odds.p.rapidapi.com
Query params:
  daysFrom=3
  regions=us
  markets=h2h,spreads,totals
```

### Response shape
Same as `/v4/sports/{sport_key}/odds` above, but not filtered by sport.

### New API
- **Endpoint:** _TBD (optional — may not be needed if `get_sport_odds` covers everything)_
- **Query params:** _TBD_
- **Response shape:** _TBD_
- **Mapping notes:** _TBD_

---

## 5. Team search — Look up a team by name

### Where it lives
- **File:** [core/event/crons/teamUpdate.py](../core/event/crons/teamUpdate.py)
- **Class/method:** `TeamCron.get_team_api(team_name)`
- **Called by:** `TeamCron.check_team(...)` → invoked from `EventCron.get_sport_events(...)` whenever a new team is seen.

### Old API call (already SofaScore — may not need changing)
```
GET https://sofascore.p.rapidapi.com/teams/search
Headers:
  X-RapidAPI-Key:  $RAPID_API_KEY
  X-RapidAPI-Host: sofascore.p.rapidapi.com
Query params:
  name={team_name}
```

### Response shape
```json
{
  "teams": [
    {
      "id": 2697,
      "name": "Dallas Cowboys",
      "country": {
        "name": "USA",
        "alpha2": "US"
      }
    }
  ]
}
```

### Fields consumed
`teams[0].id`, `teams[0].country.name`, `teams[0].country.alpha2`.

### New API
- **Endpoint:** _Same — SofaScore already. Confirm or replace._
- **Query params:** _TBD_
- **Response shape:** _TBD_
- **Mapping notes:** _TBD_

---

## 6. Team logo — Binary PNG

### Where it lives
- **File:** [core/event/crons/teamUpdate.py](../core/event/crons/teamUpdate.py)
- **Class/method:** `TeamCron.get_logo(team_id, ...)`
- **Called by:** `TeamCron.check_team(...)` right after a successful `get_team_api`.

### Old API call (already SofaScore)
```
GET https://sofascore.p.rapidapi.com/teams/get-logo
Headers:
  X-RapidAPI-Key:  $RAPID_API_KEY
  X-RapidAPI-Host: sofascore.p.rapidapi.com
Query params:
  teamId={team_id}
```

### Response shape
Binary PNG bytes (not JSON). Stored directly as `Team.logo_url` via `SimpleUploadedFile`.

### New API
- **Endpoint:** _Same — SofaScore already. Confirm or replace._
- **Query params:** _TBD_
- **Response shape:** _TBD_
- **Mapping notes:** _TBD_

---

## Django models — Target schema the new API must populate

Whatever SofaScore returns needs to be transformed into these rows.

### `Sport` — [core/event/models/sport.py](../core/event/models/sport.py)
| Field | Type | Notes |
|---|---|---|
| `key` | CharField(255), **primary key** | sport identifier, e.g. `americanfootball_nfl` |
| `group` | CharField(255) | e.g. `American Football` |
| `title` | CharField(255) | e.g. `NFL` |
| `description` | CharField(255) | |
| `active` | Boolean | |
| `has_outrights` | Boolean | |

### `Event` — [core/event/models/event.py](../core/event/models/event.py)
| Field | Type | Notes |
|---|---|---|
| `id` | UUID (AbstractModel) | event UUID from provider |
| `sport_key` | CharField(255) | FK-like string to `Sport.key` |
| `sport_title` | CharField(255) | |
| `title`, `group`, `description` | CharField(255) | copied from `Sport` |
| `commence_time` | CharField(255) | ISO timestamp string |
| `completed` | Boolean | |
| `home_team` / `away_team` | CharField(255) | raw provider names |
| `home_team_team` / `away_team_team` | FK → `Team` | resolved via `TeamCron.check_team` |
| `scores` | JSONField | `[{"name": ..., "score": ...}, ...]` |
| `winner` | CharField(255) | derived in `EventSerializer.validate` |

### `Team` — [core/event/models/team.py](../core/event/models/team.py)
| Field | Type | Notes |
|---|---|---|
| `public_id` | UUID | |
| `team_name` | CharField(255), **unique** | |
| `title` | CharField(255) | sport title, e.g. `NFL` |
| `group` | CharField(255) | sport group |
| `team_id` | CharField(255) | external provider id (SofaScore `id`) |
| `logo_url` | ImageField | stored PNG |
| `country` | CharField(255) | |
| `country_code` | CharField(10) | |

### `Bookmaker` — [core/event/models/bookmaker.py](../core/event/models/bookmaker.py)
| Field | Type | Notes |
|---|---|---|
| `event` | FK → `Event` | |
| `key` | CharField(255) | e.g. `draftkings` |
| `title` | CharField(255) | e.g. `DraftKings` |
| `last_update` | DateTimeField | |

### `Market` — [core/event/models/market.py](../core/event/models/market.py)
| Field | Type | Notes |
|---|---|---|
| `bookmaker` | FK → `Bookmaker` | |
| `key` | CharField(255) | `h2h`, `spreads`, `totals`, … |
| `last_update` | DateTimeField | |

### `Outcome` — [core/event/models/outcome.py](../core/event/models/outcome.py)
| Field | Type | Notes |
|---|---|---|
| `market` | FK → `Market` | |
| `name` | CharField(50) | ≤ 50 chars |
| `price` | FloatField | American or decimal odds |
| `point` | FloatField (nullable) | spread / total line |

---

## Refactor plan (to fill in once new endpoints are known)

1. Replace `SportCron.domain` + `headers` + `get_sports()` with SofaScore equivalent.
2. Replace `EventCron.domain` + `headers`.
3. Rewrite `EventCron.get_sport_events` to transform SofaScore event payloads into the `Event` shape above.
4. Rewrite `EventCron.get_sport_odds` to transform SofaScore odds payloads into the nested `Bookmaker` → `Market` → `Outcome` shape.
5. Drop or re-home `get_upcoming_odds` if SofaScore has no equivalent.
6. `TeamCron` likely stays as-is (already SofaScore) — confirm endpoints still exist.
7. Remove `RAPID_API_HOST` swap — one host everywhere: `sofascore.p.rapidapi.com`.

---

**Fill in the `New API` sections above with the SofaScore endpoints and sample responses, and the refactor can proceed.**
