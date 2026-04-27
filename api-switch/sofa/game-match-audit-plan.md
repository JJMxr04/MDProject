# Game / Match / Bet Audit & Refactor Plan

**Scope:** rewire `core.game` and `core.match` onto the new SofaScore-backed `Event` / `Market` / `Selection` / `OddsQuote` schema and the settlement engine in [core/event/odds/settlement.py](../core/event/odds/settlement.py). Eliminate stale snapshots, dead code paths, and the live UUID bug, and make the scoring loop drive off `Selection.settlement_status` instead of `Event.completed`.

**Builds on (already shipped):**
- [refactor-plan.md](refactor-plan.md) — Event PKs are BigInt, Teams are FKs, no more odds.p RapidAPI host.
- [odds-system-plan.md](odds-system-plan.md) — `Market` / `Selection` / `OddsQuote` with deterministic ids.
- [settlement-plan.md](settlement-plan.md) — `Selection.settlement_status` is the source of truth for win/loss/push/void.
- [hockey-extension-plan.md](hockey-extension-plan.md) — extra scopes/types but no impact on game/match shape.

**Out of scope:** templates and the legacy `*_team_team` references in [core/match/templates/portal/match/my_match_detail.html](../core/match/templates/portal/match/my_match_detail.html) — needs its own pass once this refactor stabilizes the model.

---

## 0. Decisions (locked in from Q&A)

| # | Question | Decision |
|---|---|---|
| 1a | `Bet.owner_outcome_correct` cache vs derive | **Derive** from `bet.owner_outcome.settlement_status`. Drop the booleans. |
| 1b | PUSH point handling | 0 points to both. (See §3 explainer — PUSH = "tie", stake refunded, no point swing.) **Configurable constant**. |
| 1c | VOID point handling | Repick allowed inside the match window; if the match window has closed, VOID counts as 0 points. **Configurable constant**. |
| 1d | Scoring trigger | **Selection-settlement-driven**. Score is awarded the moment the player's `Selection.settlement_status` transitions out of PENDING. Faster than waiting for whole-event finish, and routes provider flags through naturally. |
| 2a | Snapshot odds at pick | **Snapshot.** New `Bet.owner_decimal_odds_at_pick` + `Bet.player_2_decimal_odds_at_pick`. Owner locks in ≥ 8h before event start; opponent locks in any time before event start. |
| 2b | Same market vs different market | Pick = a `Selection`. Opponent can pick any other `Selection` — same market (other side / over / under / draw etc.) **or** a different market on the same event. Anti-duplicate is per `(event, market)`, not per event. |
| 2c | Same event, different markets | **Allowed.** Same event same market is rejected; same event other market is fine. |
| 3a | Pick deadline | 8h before event start, every sport. |
| 3b | Match-end behavior for unpicked slots | 0 points. **`UNPICKED_SLOT_PENALTY` constant** so we can flip it to a negative later. |
| 3c | Live picks | No. Owner can only pick events ≥ 8h out; opponent can pick up to event start. |
| 3d | Reschedules | Recompute `deadline_time` on the fly from `event.start_time`. Drop the stored copy. |
| 4a/4b | Postponed / canceled | Repick allowed if match window still open. Otherwise VOID → 0 points. |
| 4c | Suspended-mid-game | Settle normally; if Selection ends VOID, the slot scores 0. |
| 5a | Golden / regular point values | Hardcoded 2 / 1. (Constants, but no admin control.) |
| 5b | `*_completed` booleans + running scores | **Drop.** Derive both from `Game.bet.*_outcome.settlement_status`. Eliminates the desync class entirely. |
| 5c | "Game completed" definition | A game is "complete" when **its bet is settled** — i.e. the relevant `Selection.settlement_status` is no longer PENDING (any of WON/LOST/PUSH/VOID). Not tied to `Event.completed`. |
| 5d | Slot left null at match end | 0 points (`UNPICKED_SLOT_PENALTY` constant). |
| 6a | 5+1 game shape | Promote to a real `MatchGame` join model with `(match, slot, owner)` so the rigid 22 FKs go away. Validation enforces the 5+1+1 (5 per player, 1 golden). |
| 6b | `Game.match_id` CharField | Replace with `match = ForeignKey(Match)` + `on_delete=CASCADE`. |
| 6c | Game snapshot fields | Drop `Game.home_team` / `Game.away_team` / `Game.commence_time` / `Game.deadline_time` / `Game.winner` / `Game.completed`. Read through `game.event`. |
| 7a | `uuid.UUID(event_id)` bug | Fix to `int(event_id)`. |
| 7b | `Bet._settle` dead code | Removed wholesale — settlement now reads `Selection.settlement_status`. |
| 7c | `Bet.market` nullable race | N/A after refactor — `Bet.market` is derived from `bet.owner_outcome.market` and never written separately. |

---

## 1. Live Bug Triage (do these first, then refactor)

These are user-visible failures on `v2` right now — they should be fixed in their own commits before the structural work, so the refactor doesn't bury them.

### 1.1 `match.py:199` — `uuid.UUID(data.get("event_id"))`
Event PKs are now `BigIntegerField`. `uuid.UUID(...)` raises `ValueError` on every pick.
**Fix (pre-refactor):**
```python
# core/match/models/match.py:199
try:
    candidate_event_id = int(data.get("event_id"))
except (TypeError, ValueError):
    return Response({'error': 'Invalid event_id'}, status=400)
if candidate_event_id in eventList:
    return Response({'error': 'This game is already been selected'}, status=400)
```

The proper fix lives in §6 (the duplicate check moves to a `(event, market)` tuple), but the one-line patch above unbreaks production today.

### 1.2 `Game.update_by_id` — bet processed flag is a no-op
[core/game/models/game.py:97-99](../core/game/models/game.py):
```python
if game.bet.is_owner_outcome_processed and game.bet.is_player_2_outcome_processed:
    game.bet.is_processed       # ← reads attribute, doesn't assign
    game.bet.save()
```
After the refactor (§4) the entire `is_processed` field is gone, so this block is deleted, not fixed. Calling out for the audit only — no patch needed.

### 1.3 `Bet._settle` is dead code today
Nothing calls `calculate_owner_choice` / `calculate_player_2_choice`. The match scoring loop in [core/match/models/match.py:145-165](../core/match/models/match.py) calls `Game.objects.get_owner_correctness(game)` which calls `Bet.objects.calculate_owner_choice` — but only inside `match_game_event_update`, which only runs from the [post_save Event signal](../core/game/signals.py) when `Event.completed` flips. So today **selections are settled by the new engine, but the `Bet.owner_outcome_correct` booleans are only computed at the moment Event.completed transitions** — and by then the new `Selection.settlement_status` is already authoritative. The booleans just duplicate it (with worse coverage: no PUSH, no VOID, no provider-flag path).

**Implication:** the entire `Bet.calculate_*` / `Bet._settle` chain can go in §4 with no behavior change. The signal stays but does scoring directly off `Selection.settlement_status`.

---

## 2. Conceptual Model (after this plan)

```
Event ──┐
        │  (FK)
Market ─┴── Selection ── settlement_status (PENDING|WON|LOST|PUSH|VOID)
                                  │
                                  │  (FK from Bet)
                                  ▼
                       owner_outcome ─┐
                                      ├─ Bet ──── Game ──── Match (via FK, not CharField)
                       player_2_outcome ┘
```

A `Game` is **one slot in a Match** held by an owner against an opponent, pointing at one `Event` (chosen by the owner) and zero, one, or two `Selection`s — owner's pick (in market A) and opponent's pick (in market A or B on the same event).

**The score for a slot is computed, never stored:**

```
points(game) = score_for(bet.owner_outcome) + score_for(bet.player_2_outcome)
score_for(selection) =
    GOLDEN_POINTS if game.is_golden else REGULAR_POINTS   if selection.settlement_status == WON
    0                                                     if selection.settlement_status == LOST
    0                                                     if selection.settlement_status == PUSH
    0                                                     if selection.settlement_status == VOID
    0                                                     if selection is None and match expired
    None  (not yet scored)                                if selection.settlement_status == PENDING
```

Match-level totals are then `sum(score_for(...) per slot)`. Live, derived, no desync.

---

## 3. PUSH vs VOID — the explainer (1b context)

I asked about PUSH because the term has a specific betting meaning that decides player UX:

| State | Meaning | What happens to a real-money bet | Our scoring (locked in 1b/1c) |
|---|---|---|---|
| **WON** | Selection hit (e.g. picked OVER 2.5, total = 3) | Stake returned + winnings | `REGULAR_POINTS` (1) or `GOLDEN_POINTS` (2) |
| **LOST** | Selection missed | Stake forfeited | 0 |
| **PUSH** | Exact tie on the line (e.g. picked OVER 2.5, total = 2.5 — only possible on integer-line totals/spreads) | Stake refunded | **0** (configurable via `PUSH_POINTS`) |
| **VOID** | Market withdrawn / event canceled / postponed past match window | Stake refunded | **0** (configurable via `VOID_POINTS`) |
| **PENDING** | Not yet settled | n/a | n/a (not scored) |

`PUSH` only fires on integer lines (totals like 2 goals, NBA spreads like ±5). Half-lines (2.5, 1.5) can't push. So in practice it's rare for soccer totals (most lines are .5) and common for NBA spreads.

Ship with `PUSH_POINTS = 0` and `VOID_POINTS = 0`. Both as constants in `core/match/scoring.py`. Easy to flip to `0.5` ("half point") later without a schema change.

---

## 4. Schema Changes

All wrapped in one new migration (`core.game/0002_*.py`, `core.match/0002_*.py`). Dev DB wipe is acceptable per §5 of the original refactor plan.

### 4.1 `Game` — strip the snapshot fields, real FK to Match

**Before** ([core/game/models/game.py:145-160](../core/game/models/game.py)):
```python
class Game(AbstractModel):
    id = UUIDField(primary_key=True, ...)
    owner = FK(User, ...)
    player_2 = FK(User, ...)
    match_id = CharField(max_length=200, default='0')          # ← string compare
    commence_time = DateTimeField(null=True)                    # ← snapshot of event.start_time
    deadline_time = DateTimeField(null=True)                    # ← snapshot of (start_time - 8h)
    completed = BooleanField(default=False)                     # ← derived from event
    home_team = CharField(max_length=200, null=True)            # ← snapshot
    away_team = CharField(max_length=200, null=True)            # ← snapshot
    winner = CharField(max_length=200, null=True)               # ← snapshot
    owner_choice = CharField(max_length=200, null=True)         # ← unused dead string
    player_2_choice = CharField(max_length=200, null=True)      # ← unused dead string
    event = FK(Event, on_delete=SET_NULL, null=True)
    bet = FK(Bet, on_delete=CASCADE, null=True)
```

**After:**
```python
class Game(AbstractModel):
    id = UUIDField(primary_key=True, ...)
    match = FK(Match, on_delete=CASCADE, related_name="games")  # ← real FK
    owner = FK(User, on_delete=CASCADE, related_name="owner_games")
    player_2 = FK(User, on_delete=CASCADE, related_name="player_2_games")
    event = FK(Event, on_delete=PROTECT, null=True, related_name="games")
    bet = OneToOneField(Bet, on_delete=CASCADE, related_name="game")
    is_golden = BooleanField(default=False)                     # ← was implicit (FK-name based)

    # everything else is derived:
    @property
    def commence_time(self):       return self.event.start_time if self.event else None
    @property
    def deadline_time(self):       return (self.commence_time - DEADLINE_BUFFER) if self.commence_time else None
    @property
    def home_team(self):           return self.event.home_team if self.event else None
    @property
    def away_team(self):           return self.event.away_team if self.event else None
    @property
    def winner(self):              return self.event.winner if self.event else None
    @property
    def is_settled(self) -> bool:
        """Both expected sides have a non-PENDING selection (or a deliberately-null one
        that will be VOIDED at match end)."""
        return self._side_settled(self.bet.owner_outcome) and self._side_settled(self.bet.player_2_outcome)
```

**Removed:** `owner_choice`, `player_2_choice` (dead strings, never written), `home_team`, `away_team`, `commence_time`, `deadline_time`, `winner`, `completed`.

`event.on_delete=PROTECT` so an event we've issued picks against can't be deleted out from under live games. Events are append-only anyway (per refactor plan §40), so this is belt-and-braces.

### 4.2 `Bet` — derived from selections, not duplicated

**Before** ([core/game/models/bet.py:91-115](../core/game/models/bet.py)):
```python
class Bet(AbstractModel):
    market = FK(Market, on_delete=SET_NULL, null=True)
    owner_outcome = FK(Selection, on_delete=SET_NULL, null=True, related_name='bet_owner_outcome')
    player_2_outcome = FK(Selection, on_delete=SET_NULL, null=True, related_name='bet_player_2_outcome')
    owner_outcome_correct = BooleanField(default=False)         # ← duplicates settlement_status
    player_2_outcome_correct = BooleanField(default=False)      # ← duplicates settlement_status
    is_owner_outcome_processed = BooleanField(default=False)    # ← duplicates settlement_status != PENDING
    is_player_2_outcome_processed = BooleanField(default=False) # ← duplicates settlement_status != PENDING
    is_processed = BooleanField(default=False)                  # ← AND of the two
```

**After:**
```python
class Bet(AbstractModel):
    owner_outcome = FK(Selection, on_delete=PROTECT, null=True, related_name='+')
    player_2_outcome = FK(Selection, on_delete=PROTECT, null=True, related_name='+')
    # Snapshot odds at pick time. Locked the moment the user submits.
    owner_decimal_odds_at_pick    = DecimalField(max_digits=8, decimal_places=4, null=True)
    player_2_decimal_odds_at_pick = DecimalField(max_digits=8, decimal_places=4, null=True)
    owner_picked_at    = DateTimeField(null=True)
    player_2_picked_at = DateTimeField(null=True)
```

**Removed:** `market` (use `owner_outcome.market`), all five booleans, and the entire `BetManager._settle` / `calculate_owner_choice` / `calculate_player_2_choice` chain. ~70 lines of dead code go.

`on_delete=PROTECT` on the selection FKs prevents accidental deletion of a selection that a Bet still references. With the new odds pipeline upserting selections idempotently on `sourceId`, deletes shouldn't happen anyway, but PROTECT enforces it.

### 4.3 `Match` — drop the 10 game FKs and 11 boolean caches

**Before** ([core/match/models/match.py:239-289](../core/match/models/match.py)):
```python
class Match(AbstractModel):
    id, player_1, player_2, winner, match_state, match_type, tiebreaker, start_date, end_date,
    player_1_score, player_2_score,
    player_1_game_1, player_1_game_1_completed,
    player_1_game_2, player_1_game_2_completed,
    ... (×10)
    golden_game, golden_game_completed,
```

**After:**
```python
class Match(AbstractModel):
    id, player_1, player_2, winner, match_state, match_type,
    tiebreaker, start_date, end_date,
    # scores derived (see §5.4); player_1_score / player_2_score become @property.
    # game FKs removed — use Match.games (related_name from Game.match)
```

Game lookup becomes:
```python
match.games.filter(owner=match.player_1, is_golden=False).order_by('slot')   # 5 rows
match.games.filter(is_golden=True)                                            # 1 row
```

Add a `slot = SmallIntegerField()` to `Game` (1..5 for regular, 0 for golden) so ordering is stable and validation is easy.

### 4.4 Validation — enforce 5+5+1 in code, not in schema

```python
# core/match/models/match.py
def assert_valid_match_layout(match: Match):
    p1_count = match.games.filter(owner=match.player_1, is_golden=False).count()
    p2_count = match.games.filter(owner=match.player_2, is_golden=False).count()
    g_count  = match.games.filter(is_golden=True).count()
    assert p1_count == 5, f"Match {match.id} has {p1_count} player_1 slots (expected 5)"
    assert p2_count == 5, f"Match {match.id} has {p2_count} player_2 slots (expected 5)"
    assert g_count == 1,  f"Match {match.id} has {g_count} golden slots (expected 1)"
```

Add a Django `CheckConstraint`-friendly partial unique index: `(match_id, owner_id, slot, is_golden)` so we never accidentally create two slot-3s for the same player.

### 4.5 Migration plan
Three migrations in order, all fresh-DB (dev wipe):
1. `core/game/migrations/0002_game_match_fk_and_strip_snapshots.py` — adds `match` FK, `is_golden`, `slot`; drops snapshot fields; drops `owner_choice`, `player_2_choice`, `match_id`.
2. `core/game/migrations/0003_bet_drop_settlement_cache.py` — drops the 5 booleans + `market`; adds the snapshot-odds fields + `picked_at` timestamps.
3. `core/match/migrations/0002_match_drop_game_fks_and_completed_booleans.py` — drops the 10 `*_game_N` FKs, the 11 `*_completed` booleans, and the `player_1_score` / `player_2_score` integer fields.

Migrations 1 and 3 must run together (Match readers reference Game; Game readers reference Match). Sequence by `dependencies=` so both apply atomically.

---

## 5. Behavioral Refactor

### 5.1 Picking — `Game.objects.upload_pick` (replaces `Match.objects.upload_pick` + `Game.objects.update_by_id`)

The two existing entry points overlap and both have quirks. Collapse into one:

```python
# core/game/models/game.py

DEADLINE_BUFFER = timedelta(hours=8)   # all sports, locked per Q3a

class GameManager(AbstractManager):
    def upload_pick(self, *, current_user, match, event_id: int, selection_id: int) -> tuple[Game, str]:
        """Owner or opponent picks a Selection.

        Returns (game, status) where status ∈ {"created", "owner_picked", "opponent_picked", "repicked"}.
        Raises PickError on validation failures.
        """
        # 1) Auth
        if current_user not in (match.player_1, match.player_2):
            raise PickError("Not a participant")
        if match.match_state != 'accepted':
            raise PickError("Match not active")

        # 2) Resolve selection -> market -> event
        selection = Selection.objects.select_related("market", "market__event").get(pk=selection_id)
        if selection.market.event_id != event_id:
            raise PickError("Selection does not belong to that event")

        # 3) Find the slot. Owner takes the first empty slot for their side.
        is_owner_pick = current_user == match.player_1   # convention: player_1 owns p1 slots
        ...
```

Key rules baked in:
- **Owner deadline:** `event.start_time - now >= 8h` (per 3a/3c). Owner can't open a slot inside that window.
- **Opponent deadline:** `event.start_time - now > 0` — opponent has up until the event starts, but can't pick post-start (per 3c).
- **Anti-duplicate:** the same `(event, market)` cannot appear twice across all 11 slots in this match. Same event different market is allowed (per 2b/2c). The current code blocks all duplicate events — this needs to relax to `(event_id, market_id)`.
- **Snapshot odds:** capture `Bet.owner_decimal_odds_at_pick = selection.decimal_odds` and `owner_picked_at = now()` at insert time. Locked-in for scoring history; the current `selection.decimal_odds` can drift afterwards.

### 5.2 Repick (postponed / canceled events) — `Game.objects.repick`

Per 4a/4b — when an Event transitions to `postponed` or `canceled` and the match window is still open, the affected slot should be re-pickable. Implementation:

```python
# core/event/odds/settlement.py — settle_event already voids selections.
# Add a sibling that nulls out the bet linkage so the slot is "empty" again.

def reopen_games_for_voided_event(event: Event) -> int:
    """When an event becomes void/canceled, drop any Bet outcomes pointing
    at that event's selections so the slot reopens for repicking."""
    if event.status_type not in ("canceled", "postponed"):
        return 0
    affected = Bet.objects.filter(
        Q(owner_outcome__market__event=event) | Q(player_2_outcome__market__event=event)
    ).select_related("game", "game__match")
    reopened = 0
    for bet in affected:
        if bet.game.match.end_date <= timezone.now():
            continue   # match window closed → leave VOID, scores 0
        if bet.owner_outcome and bet.owner_outcome.market.event_id == event.id:
            bet.owner_outcome = None
            bet.owner_decimal_odds_at_pick = None
        if bet.player_2_outcome and bet.player_2_outcome.market.event_id == event.id:
            bet.player_2_outcome = None
            bet.player_2_decimal_odds_at_pick = None
        bet.save(update_fields=[...])
        # Also reset Game.event so picker can pick a fresh event in the slot
        bet.game.event = None
        bet.game.save(update_fields=["event"])
        reopened += 1
    return reopened
```

Hook this into `Event.objects.upsert_from_payload` next to the existing `_should_settle` call:
```python
if obj.status_type in ("postponed", "canceled") and (previous is None or previous.status_type != obj.status_type):
    reopen_games_for_voided_event(obj)
```

### 5.3 Scoring — derived, settlement-driven (replaces `match_game_event_update`)

The current loop in [core/match/models/match.py:81-168](../core/match/models/match.py) does ~85 lines of bookkeeping with a 10-arm if/elif tree per slot. Drop the whole thing.

```python
# core/match/scoring.py  (new)

REGULAR_POINTS = 1
GOLDEN_POINTS  = 2
PUSH_POINTS    = 0          # configurable per Q1b
VOID_POINTS    = 0          # configurable per Q1c
UNPICKED_SLOT_PENALTY = 0   # configurable per Q3b/5d


def points_for_selection(selection: Optional[Selection], *, is_golden: bool, match_window_closed: bool) -> Optional[int]:
    """Returns score for one side of one game, or None if not yet decided."""
    base = GOLDEN_POINTS if is_golden else REGULAR_POINTS
    if selection is None:
        return UNPICKED_SLOT_PENALTY if match_window_closed else None
    s = selection.settlement_status
    if s == "WON":     return base
    if s == "LOST":    return 0
    if s == "PUSH":    return PUSH_POINTS
    if s == "VOID":    return VOID_POINTS
    return None  # PENDING


def score_match(match: Match) -> tuple[int, int, bool]:
    """Returns (player_1_score, player_2_score, fully_decided)."""
    closed = match.end_date and match.end_date <= timezone.now()
    p1, p2, decided = 0, 0, True
    for game in match.games.select_related("bet", "bet__owner_outcome", "bet__player_2_outcome", "event"):
        for side, selection in (("owner", game.bet.owner_outcome), ("player_2", game.bet.player_2_outcome)):
            pts = points_for_selection(selection, is_golden=game.is_golden, match_window_closed=closed)
            if pts is None:
                decided = False
                continue
            user = game.owner if side == "owner" else game.player_2
            if user == match.player_1:   p1 += pts
            elif user == match.player_2: p2 += pts
    return p1, p2, decided
```

`Match.player_1_score` / `Match.player_2_score` become `@property` that call `score_match(self)[0]` / `[1]`. No write path.

### 5.4 Settlement signal — drives match completion

Replace the post-Event-save signal with a post-Selection-save signal so scoring fires off the actual decision boundary (per 1d):

```python
# core/game/signals.py

@receiver(post_save, sender=Selection)
def settlement_propagated(sender, instance, **kwargs):
    if instance.settlement_status == "PENDING":
        return
    bets = Bet.objects.filter(
        Q(owner_outcome=instance) | Q(player_2_outcome=instance)
    ).select_related("game", "game__match")
    matches = {bet.game.match_id: bet.game.match for bet in bets}
    for match in matches.values():
        _maybe_complete_match(match)


def _maybe_complete_match(match: Match):
    if match.match_state == "completed":
        return
    p1, p2, decided = score_match(match)
    if not decided:
        # window may also close us out (handles unpicked slots + voided events)
        if not (match.end_date and match.end_date <= timezone.now()):
            return
    Match.objects.calculate_winner(match)   # uses derived score_match() internally
```

`Match.objects.calculate_winner` simplifies to:
```python
def calculate_winner(self, match: Match):
    p1, p2, _ = score_match(match)
    if p1 > p2:   match.winner = match.player_1
    elif p2 > p1: match.winner = match.player_2
    else:         match.winner = TieBreaker.objects.calculate_winner(match.tiebreaker)
    match.match_state = "completed"
    match.save(update_fields=["winner", "match_state"])
    # send emails as before
```

### 5.5 Cron — `MatchCron.completeMatches`

Already loops finished-window matches and calls `calculate_winner`. Stays. But add a sibling pass to mark unpicked slots as scored-zero by triggering `_maybe_complete_match`:

```python
# core/match/crons/matchUpdate.py
def completeMatches(self):
    cutoff = timezone.now()
    for match in Match.objects.filter(end_date__lte=cutoff, match_state='accepted'):
        _maybe_complete_match(match)
```

Same call cost (zero — pure DB).

---

## 6. Touchpoint Audit

Files that read removed fields and need updating in this same pass:

| File | What to change |
|---|---|
| [core/game/models/game.py](../core/game/models/game.py) | Whole file rewrite per §4.1, §5.1, §5.2. |
| [core/game/models/bet.py](../core/game/models/bet.py) | Strip `_settle` chain, the 5 booleans, `market` field. Keep selection FKs + add snapshot-odds fields. |
| [core/game/admin.py](../core/game/admin.py) | Remove `commence_time`, `deadline_time`, `home_team`, `away_team`, `winner`, `match_id`. Add `match`, `slot`, `is_golden`, `bet__owner_outcome__settlement_status` filter. |
| [core/game/serializers/game.py](../core/game/serializers/game.py) | `to_representation` reads `home_team`/`away_team` indirectly via event — already does this for `event`; just confirm. |
| [core/game/signals.py](../core/game/signals.py) | Replace `post_save Event` handler with `post_save Selection` per §5.4. |
| [core/match/models/match.py](../core/match/models/match.py) | Drop `match_game_event_update`. Replace `accept_match` to create `Game`s through the new join, not assigning to FK fields. Replace `upload_pick` to delegate to `Game.objects.upload_pick`. Score fields → `@property`. |
| [core/match/admin.py](../core/match/admin.py) | Drop game-FK columns from list_display; add inline showing `Game` rows. |
| [core/match/serializers/match.py](../core/match/serializers/match.py) | Replace `player_1_game_1`..`golden_game` flattened representation with `games_by_player(player_1)` / `games_by_player(player_2)` / `golden_game` lookups via the related manager. |
| [core/match/views/eventMarket.py](../core/match/views/eventMarket.py) | Confirm market fetch uses `selection.market.event_id`, not Game snapshot. |
| [core/match/templates/portal/match/my_match_detail.html](../core/match/templates/portal/match/my_match_detail.html) | **Already broken** — references `event.home_team_team` and `event.commence_time`. Out of scope for this plan; track separately. |
| [core/event/models/event.py](../core/event/models/event.py) | Add `reopen_games_for_voided_event` hook in `upsert_from_payload`. |
| [core/event/odds/settlement.py](../core/event/odds/settlement.py) | Add the void-cascade helper (or put it in a `core.game.events` module to keep settlement free of game knowledge). |

The settlement engine knows nothing about Games today and that's a feature — keep it that way. The reopen helper lives in `core/game/events.py` (new file), and the Event upsert imports it next to `settle_event`.

---

## 7. Edge Cases & Open Questions

### 7.1 Provider settles before opponent picks
A live game finishes, owner had picked; opponent never picked. `Selection.settlement_status` for owner's pick goes to WON/LOST. Opponent's slot is `None`. Per 5d, `points_for_selection(None, ..., match_window_closed=False)` returns `None` (not yet decided) — opponent still has until match end_date to pick a *different* event for that slot? **Issue:** the slot is currently tied to the same event as the owner's pick. Two interpretations:

- **(A)** Each game = one event for both sides. Opponent's only choice is which selection on that event to pick. If they don't pick before the event starts, slot is auto-VOID at event-start (or 0 at match end).
- **(B)** Each game has two independent picks — owner picks event+selection, opponent picks any event+selection. Then "duplicate event" guard applies across both sides.

Reading the existing code, **(A) is the current design** — `Game.event` is one field, both `bet.owner_outcome` and `bet.player_2_outcome` reference selections on that event's markets. The new plan keeps this. Implication: when the event starts and opponent hasn't picked, mark `bet.player_2_outcome` as a sentinel "MISSED" → counts as 0 via `UNPICKED_SLOT_PENALTY`. Practically: a small cron that runs at event-start time and walks unfilled `bet.player_2_outcome` to set them to `None` permanently and lock the slot. Or simpler: just rely on `points_for_selection(None, match_window_closed=True)` at match end. Recommend the latter — fewer moving parts.

### 7.2 Snapshot odds on a moneyline that later flips suspended
We capture `decimal_odds` at pick time. Subsequent provider-suspended state doesn't matter for scoring (we trust the snapshot). For UI we should still surface "your line was 1.85, current line is 2.10". Both available: `bet.owner_decimal_odds_at_pick` and `selection.decimal_odds`.

### 7.3 Owner cancels a pick before deadline
Not in scope. Current code never supported it. If we want it later, `Game.objects.unpick(side, current_user)` clears `bet.owner_outcome` (or `player_2_outcome`) and `bet.*_at_pick` and `game.event` — same shape as the void-reopen path.

### 7.4 Tiebreaker on a voided golden game
[TieBreaker.calculate_event_total](../core/match/models/TieBreaker.py:23) reads `tiebreaker.golden_game.event.scores` — a field that **doesn't exist** on the new `Event` model (we have `home_score` / `away_score` / `scores_payload`). This is a separate live bug; fix in the same pass:
```python
def calculate_event_total(self, tiebreaker):
    event = tiebreaker.golden_game.event
    if event.home_score is None or event.away_score is None:
        return None
    tiebreaker.total = event.home_score + event.away_score
    tiebreaker.save(update_fields=["total"])
    return tiebreaker.total
```
Also: the old code did `int(scores[0]['score']) + int(scores[0]['score'])` — same index twice, so it was double-counting home and ignoring away. Fixing that here too.

If the golden game's event ends up VOID, the tiebreaker can't compute. Recommend: at match completion, if `golden_game.event.status_type` is in (`postponed`, `canceled`) and `score_match` returns a tie, fall back to `calculate_winner_random` directly with a logged note. (Out of scope of this plan to redesign tiebreakers — flag only.)

---

## 8. Implementation Order

Each step is independently shippable and verifiable.

1. **Live-bug commit** — patch §1.1 (`uuid.UUID` → `int`). One file, one line. Restores picks immediately on `v2`.
2. **Constants module** — add `core/match/scoring.py` with `REGULAR_POINTS`, `GOLDEN_POINTS`, `PUSH_POINTS`, `VOID_POINTS`, `UNPICKED_SLOT_PENALTY`, `DEADLINE_BUFFER`, plus `points_for_selection` and `score_match` helpers. Pure functions; testable in isolation.
3. **Bet refactor** — drop the 5 booleans + `market`, add snapshot-odds + `picked_at`. Migration. Update `BetManager.create_bet` and `set_*` helpers.
4. **Game refactor** — strip snapshot fields; convert `match_id` to FK; add `is_golden`, `slot`. Migration. Rewrite `Game.objects.upload_pick`, retire `update_by_id`. Properties for `commence_time`/`deadline_time`/`home_team`/`away_team`/`winner`.
5. **Match refactor** — drop the 10 game FKs and 11 booleans. Migration. Rewrite `accept_match` to create games through the join. Replace `match_game_event_update` with `_maybe_complete_match`. `player_1_score`/`player_2_score` become `@property`.
6. **Signal switch** — swap the Event post_save handler for the Selection post_save handler.
7. **Reopen hook** — add `reopen_games_for_voided_event` and wire it into `Event.objects.upsert_from_payload`.
8. **TieBreaker patch** — fix the broken `scores[0]` access.
9. **Admin / serializer update** — touchpoints from §6.
10. **Smoke test** — accept a private match → upload picks via `upload_pick` → manually settle one event → verify `score_match` returns the right tuple → verify `_maybe_complete_match` flips state when all 11 slots are decided.

Steps 3–5 hold dev-DB-wipe semantics consistent with the prior refactor. No backfill required.

---

## 9. What this plan deliberately does *not* touch

- **Templates.** [core/match/templates/portal/match/my_match_detail.html](../core/match/templates/portal/match/my_match_detail.html) is already broken from the Event refactor (it uses `event.home_team_team` and `event.commence_time`). Needs a separate template-pass plan.
- **Public match list / waitlist views.** No model fields they depend on are changing.
- **Bookmaker / Outcome / old Market.** Already orphaned by the odds plan; their cleanup is tracked there.
- **Multi-provider odds.** Per the hockey plan §9.4, multiple feeds collapse onto one Market — out of scope here.
- **Live picks.** Explicitly disallowed per 3c. The plan keeps the 8h-before-start owner deadline; opponent until start.

---

**Approve § 0 (decisions table) and §8 (implementation order) and this becomes mechanical.** Each numbered step in §8 is small enough to land as its own commit with a passing manual smoke test.
