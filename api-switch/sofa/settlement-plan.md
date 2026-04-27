# Selection Settlement Plan

**Goal:** after an event finishes, mark every `Selection` as won or lost (with full-fidelity push / void fallbacks), persist it in the DB, and expose a simple `is_winner: bool | null` field on the REST API.

**Source signal:** SofaScore's `winning: true|false` flag on choices, confirmed present on finished-game payloads (see [match_odds__american-football__15272384.json](../../sports-scores/json/match_odds__american-football__15272384.json) — 34 hits; absent on live/pre-game payloads for the other three sports). We copy the flag when we have it and compute ourselves when we don't.

**Builds on:** the completed odds pipeline. `Event` / `Market` / `Selection` / `OddsQuote` are in place. No new dependencies.

---

## 1. Overview

### The question — "where do outcomes live?"
Right now: **nowhere.** `Selection` carries only `decimal_odds` / `opening_decimal_odds` / `movement` / `suspended`. Nothing records whether the bet hit. `Event.winner` / `winner_code` tell us who won the event, but we never project that onto individual selections.

### What we're adding
Three fields on `Selection`:
- `settlement_status` — enum: `PENDING`, `WON`, `LOST`, `PUSH`, `VOID`.
- `settled_at` — DateTime, nullable. Stamp when settlement was recorded.
- `settlement_source` — enum: `PROVIDER` (from SofaScore `winning`), `COMPUTED` (our own math), `MANUAL` (admin override).

### API surface — `is_winner: bool | null`
The Flutter-facing field stays boolean-ish. One helper serializes the enum into the three states the UI actually needs:

| `settlement_status` | `is_winner` |
|---|---|
| `WON` | `true` |
| `LOST` | `false` |
| `PUSH` / `VOID` / `PENDING` | `null` (UI shows "—" or "Void") |

Push vs void is still queryable server-side via `settlement_status` for admin and analytics; the public API just folds them into `null` so the Flutter client doesn't have to care.

### Two settlement paths
1. **Provider path** — when SofaScore ships `winning: true|false` in the odds payload (happens post-game), we copy it directly. No math, trust the source.
2. **Computed path** — for selections still `PENDING` on a finished event, we run our own math against `Event.home_score` / `away_score` / `winner_code`. Covers MONEYLINE, TOTAL, SPREAD, BTTS, Double Chance, Draw No Bet. Anything requiring corners / cards / first-scorer identity stays `PENDING` until provider data lands.

### Why an enum instead of a plain bool
"Won or lost" is the 90% case. The 10% you don't want to lose:
- **Push** (integer total, exact line match) — stake returns, it's neither won nor lost.
- **Void** (game postponed, market withdrawn) — treated the same UI-wise but different for accounting.
- **Pending** — pre-event and in-play. Critical for filtering "my open bets".

Bolting PUSH/VOID onto a boolean later means a data migration. Doing it right up front costs one extra column.

---

## 2. Schema Changes

### `core/event/models/odds/selection.py`
```python
class SettlementStatus(models.TextChoices):
    PENDING = "PENDING"
    WON = "WON"
    LOST = "LOST"
    PUSH = "PUSH"
    VOID = "VOID"


class SettlementSource(models.TextChoices):
    PROVIDER = "PROVIDER"   # SofaScore's `winning` flag
    COMPUTED = "COMPUTED"   # our settlement.py math
    MANUAL = "MANUAL"       # admin override


class Selection(models.Model):
    # … existing fields …
    settlement_status = models.CharField(
        max_length=8,
        choices=SettlementStatus.choices,
        default=SettlementStatus.PENDING,
        db_index=True,
    )
    settled_at = models.DateTimeField(null=True, blank=True)
    settlement_source = models.CharField(
        max_length=16,
        choices=SettlementSource.choices,
        blank=True,
    )

    class Meta:
        db_table = "core_selection"
        indexes = [
            models.Index(fields=["market", "type"]),
            models.Index(fields=["settlement_status", "market"]),   # new
        ]
```

One small new index supports the "settle all pending selections for this event" query pattern.

### `Event`
No schema change. The existing `status_type`, `home_score`, `away_score`, `winner`, `winner_code`, `scores_payload` are enough to drive the computed path for our five core categories.

### Migration
Auto-generated `AddField` × 3 + `AddIndex` × 1. Non-destructive; existing rows default to `settlement_status=PENDING`.

---

## 3. When Settlement Runs (Triggers)

Three trigger points, each with a clear responsibility.

### 3.1 Inside `ingest_odds` (hot path — provider signal)
Every time odds are fetched and normalized, inside the per-choice loop:
```python
if "winning" in raw_choice:
    # SofaScore has decided. Copy it immediately, overrides any computed state.
    provider_flag = bool(raw_choice["winning"])
    sel.settlement_status = "WON" if provider_flag else "LOST"
    sel.settled_at = now
    sel.settlement_source = "PROVIDER"
```
Zero additional API calls — settlement rides along with every odds refresh. When a user opens a just-finished event and we hit `get-all-odds`, the response carries the winning flags and settlement lands automatically.

### 3.2 Event-finished hook (computed path)
Inside `Event.objects.upsert_from_payload` (in [core/event/models/event.py](../core/event/models/event.py)), detect the transition to `status_type="finished"` and enqueue a settlement pass for that event. Fires regardless of whether odds were refetched.

```python
# in Event.objects.upsert_from_payload, after update_or_create:
was_finished = previous_instance and previous_instance.status_type == "finished"
is_finished_now = obj.status_type == "finished"
if is_finished_now and not was_finished:
    from core.event.odds.settlement import settle_event
    settle_event(obj)   # synchronous for v1; move to Celery task later
```

### 3.3 Backfill cron (safety net)
`core.crons.tasks.settle_pending_cron` — scheduled nightly. Finds every finished event with any `PENDING` selections older than 2h and runs `settle_event` again. Idempotent. Catches:
- Events that finished while the odds service was down.
- Provider-flag updates that arrived after our last odds refresh.
- Edge bugs in the computed path that left things pending.

Schedule entry:
```python
"settle_pending_cron": {
    "task": "core.crons.tasks.settle_pending_cron",
    "schedule": crontab(hour=3, minute=30),  # nightly at 03:30 UTC
}
```

No API calls. Pure DB work.

---

## 4. Settlement Logic by Category

One function per `MarketCategory`. Dispatched in `settle_event(event)` via the `category` + `type` fields on each Market. Lives in `core/event/odds/settlement.py`.

### 4.1 `MONEYLINE` — always computable
Inputs: `event.winner_code` (1=home, 2=away, 3=draw).

```python
def settle_moneyline(event, market, selections):
    winner_by_type = {1: "HOME", 2: "AWAY", 3: "DRAW"}
    winning_type = winner_by_type.get(event.winner_code)
    if winning_type is None:
        return  # leave pending
    for sel in selections:
        if sel.type == winning_type:
            sel.settlement_status = "WON"
        elif sel.type in ("HOME", "AWAY", "DRAW"):
            sel.settlement_status = "LOST"
```

Sport-specific wrinkles:
- **`NHL_MATCH_WINNER_INC_OT`** — 2-way, winner_code ∈ {1,2}. Works as-is.
- **`NHL_MATCH_WINNER_REG`** — 3-way, but needs regulation-only winner. `Event.winner_code` reflects including OT/SO. **Can't compute** — leave pending, hope for provider flag.
- **`SOCCER_MATCH_WINNER`** — 3-way full 90. Works as-is.

### 4.2 `TOTAL` — computable when both scores known
```python
def settle_total(event, market, selections):
    if event.home_score is None or event.away_score is None or market.line is None:
        return
    total = event.home_score + event.away_score
    line = float(market.line)
    for sel in selections:
        if sel.type == "OVER":
            if total > line: sel.settlement_status = "WON"
            elif total < line: sel.settlement_status = "LOST"
            else: sel.settlement_status = "PUSH"
        elif sel.type == "UNDER":
            if total < line: sel.settlement_status = "WON"
            elif total > line: sel.settlement_status = "LOST"
            else: sel.settlement_status = "PUSH"
```

Integer lines push. Half-lines never push.

### 4.3 `SPREAD` — computable, home-perspective line
```python
def settle_spread(event, market, selections):
    if event.home_score is None or event.away_score is None or market.line is None:
        return
    margin = event.home_score - event.away_score           # home perspective
    adjusted = margin + float(market.line)                 # line stored home-side
    for sel in selections:
        if sel.type == "HOME":
            if adjusted > 0:  sel.settlement_status = "WON"
            elif adjusted < 0: sel.settlement_status = "LOST"
            else:              sel.settlement_status = "PUSH"
        elif sel.type == "AWAY":
            if adjusted < 0:  sel.settlement_status = "WON"
            elif adjusted > 0: sel.settlement_status = "LOST"
            else:              sel.settlement_status = "PUSH"
```

Soccer Asian handicaps with `.25` / `.75` lines (stake-split markets) are **not fully correct** with this logic — they should half-win / half-lose. For v1 we treat them as a regular 2-way market (closer to the bigger half). Note in code and fall back to the provider flag when possible.

### 4.4 `PROPS_GAME` — per-type
Dispatch by `market.type`:

| `type` | Logic |
|---|---|
| `SOCCER_BTTS` / `NHL_BTTS` | YES if both `home_score > 0` and `away_score > 0`, else NO. |
| `SOCCER_DOUBLE_CHANCE` | `1X` wins on winner_code ∈ {1,3}; `X2` on {2,3}; `12` on {1,2}. |
| `SOCCER_DRAW_NO_BET` | Moneyline logic, but `winner_code == 3` → PUSH for all. |
| `SOCCER_FIRST_SCORER` / `NHL_FIRST_GOAL_SCORER_TEAM` | Requires identity of the first-goal team — not in our Event schema. Leave PENDING; rely on provider flag. |
| `SOCCER_CORNERS_TOTAL` / `SOCCER_CARDS_TOTAL` | Requires corner / card counts — not in our Event schema. PENDING. |
| `NHL_OVERTIME_YES_NO` | True if event went past regulation. Currently no clean signal on the Event row; PENDING. |
| `NHL_EMPTY_NET_GOAL` | Requires empty-net event flag. PENDING. |

### 4.5 `PROPS_TEAM` — per-type
| `type` | Logic |
|---|---|
| `SOCCER_TEAM_TOTAL_GOALS` | Market has `side=HOME` or `side=AWAY`. Compare that side's score to `market.line` → OVER/UNDER/PUSH. |
| `NHL_TEAM_TOTAL_GOALS` | Same pattern. |
| `NHL_TEAM_POWER_PLAY_GOALS`, `NHL_TEAM_PENALTY_MINUTES` | Requires split stats we don't store. PENDING. |

### 4.6 Dispatch table
```python
# core/event/odds/settlement.py

SETTLEMENT_FUNCS = {
    "MONEYLINE":  settle_moneyline,
    "TOTAL":      settle_total,
    "SPREAD":     settle_spread,
    "PROPS_GAME": settle_props_game,   # inner switch on type
    "PROPS_TEAM": settle_props_team,   # inner switch on type
}

def settle_event(event):
    """Settle every pending selection on a finished event using computed math."""
    if event.status_type != "finished":
        return
    now = timezone.now()
    markets = Market.objects.filter(event=event).prefetch_related("selections")
    for m in markets:
        pending = [s for s in m.selections.all() if s.settlement_status == "PENDING"]
        if not pending:
            continue
        fn = SETTLEMENT_FUNCS.get(m.category)
        if fn is None:
            continue
        fn(event, m, pending)
        for s in pending:
            if s.settlement_status != "PENDING":
                s.settled_at = now
                s.settlement_source = "COMPUTED"
        Selection.objects.bulk_update(
            pending, ["settlement_status", "settled_at", "settlement_source"]
        )
```

---

## 5. Provider-Flag Path (authoritative)

Inside `ingest_odds` (modify [core/event/odds/normalize.py](../core/event/odds/normalize.py)):

```python
# inside the per-choice loop, after upsert
if "winning" in raw_choice and raw_choice["winning"] is not None:
    new_status = "WON" if raw_choice["winning"] else "LOST"
    if sel.settlement_status != new_status:
        sel.settlement_status = new_status
        sel.settled_at = now
        sel.settlement_source = "PROVIDER"
        sel.save(update_fields=["settlement_status", "settled_at", "settlement_source"])
```

Provider always wins over COMPUTED. If a provider flag arrives after we computed LOST and it says LOST, no change. If they disagree, trust the provider and overwrite. Log the disagreement for auditing.

---

## 6. Manual Override (admin source)

Admin view on `Selection` exposes `settlement_status`, `settled_at`, `settlement_source` as editable for ops. When an admin saves a change, set `settlement_source="MANUAL"` automatically so we know provider/computed can't later overwrite it.

```python
# core/event/odds/settlement.py
def mark_manual(selection, status):
    selection.settlement_status = status
    selection.settlement_source = "MANUAL"
    selection.settled_at = timezone.now()
    selection.save(update_fields=["settlement_status", "settled_at", "settlement_source"])
```

Priority order during any settlement pass:
```
MANUAL > PROVIDER > COMPUTED > PENDING
```

A `MANUAL` row is never auto-overwritten; a `PROVIDER` row is only overwritten by MANUAL; `COMPUTED` can be upgraded to PROVIDER when a newer flag arrives.

---

## 7. Query & API Exposure

### 7.1 Selection serializer update
```python
# core/event/serializers/selection.py
class SelectionSerializer(serializers.ModelSerializer):
    # existing fields …
    is_winner = serializers.SerializerMethodField()

    class Meta:
        model = Selection
        fields = [
            "selection_id", "type", "label", "odds", "movement", "suspended",
            "is_winner", "settlement_status",   # new
        ]

    def get_is_winner(self, obj):
        if obj.settlement_status == "WON":   return True
        if obj.settlement_status == "LOST":  return False
        return None   # PENDING, PUSH, VOID
```

`settlement_status` is also serialized raw so clients that care can distinguish PUSH/VOID from PENDING.

### 7.2 New REST filter
```
GET /api/events/{event_id}/markets
    ?settled=true|false         # true → status in (WON,LOST,PUSH,VOID); false → PENDING
    ?winners_only=true           # status == WON
```

Both optional. Implementation is a one-liner against the new index.

### 7.3 Admin surface
`SelectionAdmin.list_display` gets `settlement_status` + `settled_at`; `list_filter` gets `settlement_status`, `settlement_source`. Makes ops triage trivial.

---

## 8. Edge Cases

### 8.1 Pushes (integer lines only)
- Totals at integer goals / points: exact equality → PUSH. Stakes return.
- Spreads at integer lines (NFL key numbers like ±3, ±7): same rule.
- Asian handicaps at half-lines (.5, 1.5): never push.
- Quarter-lines (.25 / .75): **simplified for v1** — treat as straight WON/LOST. Provider flag is authoritative here; don't rely on our computation.

### 8.2 Voids
Event status ∈ {`postponed`, `canceled`, `notstarted` indefinitely}. For any non-finished event with age > 7 days past `start_time`, a weekly cron marks all its pending selections as `VOID` + `settlement_source="COMPUTED"`. This is the only status that's terminal without the event being finished.

### 8.3 Suspended mid-game and never reinstated
If a market was `suspended=True` when the event finished, its selections are still settleable from scores — but the book may choose to void. We default to computing normally; admins can override via MANUAL.

### 8.4 Provider flag missing for some choices only
Seen in the wild: provider flags only half the choices (e.g. only the two winners in a multi-outcome exact-score market). The other choices stay PENDING until the backfill cron runs `settle_event`, which then marks them LOST via computed if possible.

### 8.5 Provider flag disagrees with our math
Trust the provider. Log at WARN with (`selection.id`, `our_status`, `their_status`) for audit. Never silent.

### 8.6 Event score updates post-settlement
If a final score gets corrected by SofaScore after we've settled (rare but real — score-correction feeds), the `Event.updated` timestamp changes but `settle_event` is already done. Solution: on any event-ingest upsert where `home_score` or `away_score` *changed* and `status_type == "finished"`, re-trigger `settle_event`. The priority order (MANUAL > PROVIDER > COMPUTED) protects manual overrides.

### 8.7 Bet rollup (out of scope, deliberately)
The existing `Bet.owner_outcome_correct` / `Bet.player_2_outcome_correct` booleans become **derivable** from `selection.settlement_status` once this ships. Simpler to leave them alone for this plan and delete them in a follow-up, replacing reads with `bet.owner_outcome.settlement_status == "WON"`. One sweep; not gating on this plan.

### 8.8 Historical data backfill
Selections ingested before this plan all default to `PENDING`. The first nightly backfill cron pass will settle all of them against finished events. No explicit data migration required.

---

## 9. Implementation Order

1. **Add fields + migration** — `Selection` gets 3 new fields + 1 index (non-destructive).
2. **Serializer update** — `is_winner` + `settlement_status` on the API response.
3. **Provider path** — 6-line addition inside `ingest_odds` normalizer loop.
4. **Computed path** — new file `core/event/odds/settlement.py` with the 5 functions + dispatcher.
5. **Event-finished hook** — small addition in `Event.objects.upsert_from_payload`.
6. **Backfill cron** — `settle_pending_cron` task + beat schedule entry.
7. **Admin** — add the new fields to `SelectionAdmin`.
8. **Smoke test** — pick a finished soccer event, run `get_event_odds(event, force=True)` to pull the `winning` flags; verify `Selection.settlement_status` gets set correctly and `is_winner` surfaces through the API.

### Budget impact
- **0 additional SofaScore calls.** Provider path rides on existing `get_event_odds` calls. Computed path is pure DB. Cron is pure DB.
- One extra DB column write per affected Selection per settlement pass — negligible.

---

**Approve and I'll implement 1→8. Each step is small and independently verifiable. No unknown unknowns — the schema and the two flag sources are both confirmed.**
