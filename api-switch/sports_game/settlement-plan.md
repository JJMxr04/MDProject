# Settlement Plan — SportsGameOdds Edition

**Goal:** keep the existing settlement engine and its `Selection.settlement_status` enum intact, but replace the SofaScore-flavored "provider" path with one driven by SGO's per-odd `score` field. Computed-path math stays the same; PROVIDER source overrides COMPUTED, MANUAL overrides both, exactly as in [sofa settlement-plan.md](../sofa/settlement-plan.md).

**Builds on:** the shipped settlement engine in [core/event/odds/settlement.py](../../core/event/odds/settlement.py). All Selection enum values, the priority order MANUAL > PROVIDER > COMPUTED > PENDING, and the `settle_event` / `settle_pending_events` cron entry points are unchanged.

**This plan is intentionally a delta.** Re-read the sofa settlement plan for the full theory; only changes are below.

---

## 1. What stays unchanged

- `SettlementStatus` enum: PENDING / WON / LOST / PUSH / VOID.
- `SettlementSource` enum: PROVIDER / COMPUTED / MANUAL.
- Priority order: MANUAL > PROVIDER > COMPUTED > PENDING.
- `settle_event(event)` entry point — fired on `Event.upsert_from_payload` when status transitions to `finished`.
- `settle_pending_events(lookback_hours)` cron — nightly catch-up.
- `apply_provider_flag(sel, won)` — public function to set a selection from an authoritative provider signal.
- The `is_winner: bool | null` REST field and its mapping in [SelectionSerializer.get_is_winner](../../core/event/serializers/selection.py).
- The auto-VOID-after-7-days rule in `settle_pending_events`.
- Manual override path through Django admin.

If a behavior isn't called out in §2 or §3 below, **it stays as-is**.

---

## 2. The new PROVIDER signal — `odd.score` instead of `choice.winning`

### 2.1 Where it comes from

SGO ships a `score` field on each odd entry once the event reaches `status.finalized=true`. The `score` is the final value of the underlying stat, scoped to the entity and period the odd cares about. Examples:

| oddID | After finalization | What it means |
|---|---|---|
| `points-home-game-ml-home` | `score: 27` | Home team scored 27 points in regulation+OT (or whatever the league treats as full game). |
| `points-away-game-ml-away` | `score: 24` | Away team scored 24. |
| `points-all-game-ou-over` | `score: 51` | Total points = 51. |
| `goals-all-reg-ml3way-draw` | `score: 1` (each side scored 1, regulation only) | Used together with home/away values to pick the 3-way winner. |
| `runs-all-1st5-ou-over` | `score: 4` | Total runs scored in first 5 innings = 4. |

So the **PROVIDER path becomes a small grader function** that takes an `(odd_payload, status)` pair and returns one of `WON / LOST / PUSH / None` (None means provider can't decide — fall back to COMPUTED or PENDING).

### 2.2 The grader

Add to [core/event/odds/settlement.py](../../core/event/odds/settlement.py):

```python
def grade_from_sgo_odd(odd: dict, status: dict) -> SettlementStatus | None:
    """Returns WON/LOST/PUSH from a finalized SGO odd, or None if ungradable.

    Provider-authoritative — overrides COMPUTED for the matching Selection.
    Trust this whenever it returns non-None and status.finalized is true.
    """
    if not status.get("finalized"):
        return None
    if status.get("cancelled"):
        return SettlementStatus.VOID
    score = odd.get("score")
    if score is None:
        return None  # SGO didn't grade — defer to COMPUTED

    bet = odd.get("betTypeID")
    side = odd.get("sideID")

    if bet == "ml":
        # We can't grade an ML bet from one odd alone — need the opposing odd's score
        # for total/spread comparison. Return None and let the per-event grader (§2.3)
        # compute it. Detailed comment-only handling below.
        return None

    if bet == "ml3way":
        # Same — needs all three odds' scores to pick the winner. Defer.
        return None

    if bet == "ou":
        line_str = odd.get("closeBookOverUnder") or odd.get("bookOverUnder") or odd.get("fairOverUnder")
        if line_str is None: return None
        line = float(line_str)
        if score == line:               return SettlementStatus.PUSH
        if side == "over":              return SettlementStatus.WON if score > line else SettlementStatus.LOST
        if side == "under":             return SettlementStatus.WON if score < line else SettlementStatus.LOST
        return None

    if bet == "sp":
        line_str = odd.get("closeBookSpread") or odd.get("bookSpread") or odd.get("fairSpread")
        if line_str is None: return None
        line = float(line_str)
        # SGO ships `score` on each side as that side's stat value; for spreads we need
        # the perspective margin. Same defer-to-grader logic as ml.
        return None

    if bet == "yn":
        if score in (0, 1):
            won = (score == 1)
            return SettlementStatus.WON if (won and side == "yes") or (not won and side == "no") else SettlementStatus.LOST
        return None

    if bet == "eo":
        is_even = (int(score) % 2 == 0)
        return SettlementStatus.WON if (is_even and side == "even") or (not is_even and side == "odd") else SettlementStatus.LOST

    return None
```

The function intentionally returns `None` for `ml` / `ml3way` / `sp` — those need both sides of the market to grade. See §2.3.

### 2.3 The per-event grader

```python
def grade_event_from_sgo(event: Event, odds_payload: dict, status: dict) -> int:
    """Walk an SGO event payload after status.finalized and settle every gradable
    Selection from the PROVIDER source. Returns count of selections graded.

    Called from ingest_odds_sgo for finalized events; idempotent."""
    if not status.get("finalized"):
        return 0
    now = timezone.now()
    graded = 0

    # Index odds by the (statID, statEntityID, periodID, betTypeID) tuple so we can
    # find sibling odds for ML/SP/ML3WAY grading.
    by_market: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for odd_id, odd in odds_payload.items():
        parts = parse_odd_id(odd_id)
        key = (parts["statID"], parts["statEntityID"], parts["periodID"], parts["betTypeID"])
        # Special: ml/ml3way collapse "home" + "away" into a single market group keyed
        # by ("statID", "_", "periodID", "ml"); same for sp.
        if parts["betTypeID"] in ("ml", "ml3way", "sp"):
            key = (parts["statID"], "_", parts["periodID"], parts["betTypeID"])
        by_market[key][parts["sideID"]] = odd

    for (stat_id, _, period, bet_type), sides in by_market.items():
        if bet_type == "ml":
            graded += _grade_ml(sides, event, now)
        elif bet_type == "ml3way":
            graded += _grade_ml3way(sides, event, now)
        elif bet_type == "sp":
            graded += _grade_spread(sides, event, now)
        else:
            for side, odd in sides.items():
                result = grade_from_sgo_odd(odd, status)
                if result is None: continue
                _apply_provider(odd, result, event, now)
                graded += 1

    return graded


def _grade_ml(sides: dict[str, dict], event: Event, now) -> int:
    # 2-way ML: need both home and away scores
    h, a = sides.get("home"), sides.get("away")
    if not h or not a or h.get("score") is None or a.get("score") is None: return 0
    home_won = h["score"] > a["score"]
    _apply_provider(h, SettlementStatus.WON if home_won else SettlementStatus.LOST, event, now)
    _apply_provider(a, SettlementStatus.WON if not home_won else SettlementStatus.LOST, event, now)
    return 2

def _grade_ml3way(sides, event, now) -> int:
    h, a, d = sides.get("home"), sides.get("away"), sides.get("draw")
    if not (h and a and d): return 0
    if h.get("score") is None or a.get("score") is None: return 0
    if h["score"] > a["score"]:   results = (SettlementStatus.WON, SettlementStatus.LOST, SettlementStatus.LOST)
    elif a["score"] > h["score"]: results = (SettlementStatus.LOST, SettlementStatus.WON, SettlementStatus.LOST)
    else:                         results = (SettlementStatus.LOST, SettlementStatus.LOST, SettlementStatus.WON)
    _apply_provider(h, results[0], event, now)
    _apply_provider(a, results[1], event, now)
    _apply_provider(d, results[2], event, now)
    return 3

def _grade_spread(sides, event, now) -> int:
    h, a = sides.get("home"), sides.get("away")
    if not h or not a: return 0
    if h.get("score") is None or a.get("score") is None: return 0
    line_str = h.get("closeBookSpread") or h.get("bookSpread") or h.get("fairSpread")
    if line_str is None: return 0
    line = float(line_str)  # home perspective; e.g. -3.5 means home favored by 3.5
    margin = h["score"] - a["score"]
    adjusted = margin + line   # SGO documents spread as already home-perspective signed
    if adjusted > 0:    home_status, away_status = SettlementStatus.WON, SettlementStatus.LOST
    elif adjusted < 0:  home_status, away_status = SettlementStatus.LOST, SettlementStatus.WON
    else:               home_status, away_status = SettlementStatus.PUSH, SettlementStatus.PUSH
    _apply_provider(h, home_status, event, now)
    _apply_provider(a, away_status, event, now)
    return 2

def _apply_provider(odd: dict, status: SettlementStatus, event: Event, now) -> None:
    # Synthesize the Selection PK we used at ingest time.
    parts = parse_odd_id(odd["oddID"])
    market_id = build_market_id_from_parts(event.id, parts, odd)
    sel_id = f"{market_id}:{parts['statEntityID']}-{parts['sideID']}"
    Selection.objects.filter(id=sel_id).exclude(settlement_source=SettlementSource.MANUAL).update(
        settlement_status=status,
        settled_at=now,
        settlement_source=SettlementSource.PROVIDER,
    )
```

### 2.4 Where this is called

Inside `ingest_odds_sgo` (introduced in [odds-system-plan.md §5](odds-system-plan.md)):

```python
def ingest_odds_sgo(event, odds_payload, *, status=None):
    # ... existing upsert logic ...

    # Settlement runs along with ingest — no separate call.
    if status and status.get("finalized"):
        graded = grade_event_from_sgo(event, odds_payload, status)
        logger.info("Provider-graded %d selections on %s", graded, event.id)
```

That's it. The PROVIDER path runs every time an odds payload includes a finalized event — both during the event-list cron and during user-triggered detail-page refreshes.

---

## 3. The COMPUTED path — what changes, what doesn't

### 3.1 Inputs change shape

The existing `settle_event(event)` reads `event.home_score`, `event.away_score`, `event.winner_code`, `market.line`. **These fields stay**, but their populations come from a different place.

Old: SofaScore embeds `homeScore.current` and `awayScore.current` in the event-list response.
New: SGO has no top-level scores on the event. We derive them by:

```python
def derive_event_scores(event: Event, odds_payload: dict, status: dict) -> tuple[int|None, int|None]:
    """Pull home/away scores from the canonical points/goals/runs odds."""
    if not status.get("finalized"):
        return None, None
    canonical_stat = {"FOOTBALL": "points", "BASKETBALL": "points", "HOCKEY": "goals",
                      "BASEBALL": "runs", "SOCCER": "goals"}.get(event.sport_id)
    if not canonical_stat:
        return None, None
    h_id = f"{canonical_stat}-home-game-ml-home"
    a_id = f"{canonical_stat}-away-game-ml-away"
    h = odds_payload.get(h_id, {}).get("score")
    a = odds_payload.get(a_id, {}).get("score")
    return (int(h) if h is not None else None,
            int(a) if a is not None else None)
```

Then inside `Event.objects.upsert_from_payload`:
```python
home_score, away_score = derive_event_scores(event, payload.get("odds") or {}, payload["status"])
event.home_score, event.away_score = home_score, away_score
event.winner_code = (1 if home_score > away_score else
                     2 if away_score > home_score else
                     3 if home_score is not None else None)
```

After this, every existing settler in [settlement.py](../../core/event/odds/settlement.py) (`settle_total`, `settle_spread`, `settle_moneyline`, `settle_props_game`, `settle_props_team`) **works with no further changes**. They read `event.home_score / away_score / winner_code / market.line` — populated identically.

### 3.2 Per-category settlement — no change

Re-read [sofa settlement-plan.md §4](../sofa/settlement-plan.md). All five settlers (MONEYLINE, TOTAL, SPREAD, PROPS_GAME, PROPS_TEAM) are reused verbatim. The `MarketCategory` mapping in [SETTLEMENT_FUNCS](../../core/event/odds/settlement.py) stays.

The PROPS_GAME inner switch on `Market.type` carries forward, but **most of its cases never fire under PROVIDER** — SGO's per-odd `score` covers BTTS / DNB / DC / corners / cards via the generic grader in §2.2. The COMPUTED branch acts as a safety net for events that finalize without `score` data (rare, but it happens for unusual stat types).

### 3.3 What the grader can't decide is what stays PENDING

If both PROVIDER (no `score` shipped) and COMPUTED (no derivable inputs) come up empty, the Selection stays PENDING and the nightly `settle_pending_events` cron retries. After 7 days, `settle_pending_events` auto-VOIDs the stragglers — same as today.

---

## 4. Push handling

SGO doesn't ship a "push" flag explicitly — it just reports a `score` that happens to equal the line. The grader in §2.2 detects this for `ou` markets directly. For `sp` markets the per-event grader compares margin + signed line == 0.

For `ml` / `ml3way`: **no push concept** under SGO data. If two teams tie in regulation in a 2-way ML market on a sport that allows ties, SGO's data treats this as either VOID (refund) or as a regular outcome based on book convention. The grader leaves it PENDING; admin can MANUAL-override after consulting the book.

---

## 5. Cancellation / postponement → VOID

Same trigger as sofa plan. When `Event.upsert_from_payload` sees the status transition to `cancelled` (SGO `status.cancelled=true`) or `postponed` (`status.delayed=true` past start_time + 4h), it calls:
```python
Selection.objects.filter(market__event=event).exclude(settlement_status__in=("WON", "LOST")).update(
    settlement_status=SettlementStatus.VOID,
    settled_at=now,
    settlement_source=SettlementSource.PROVIDER,
)
```
and triggers `reopen_games_for_voided_event(event)` in `core/game/events.py` exactly as today (the existing `match_window_open` repick logic carries forward unchanged — see [game-match-audit-plan.md §5.2](../sofa/game-match-audit-plan.md)).

---

## 6. Reconciliation — the once-a-day catch-up

The `settle_pending_events` cron from [sofa settlement-plan §3.3](../sofa/settlement-plan.md) stays as-is, with one tweak: when it discovers a finished-but-pending event, it now calls a new helper:

```python
def reconcile_event_via_sgo(event: Event):
    """Pull the finalized event payload from SGO and re-run grading + settle.
    Used by the nightly cron to catch events where the in-pass grader missed."""
    client = SportsGameOddsClient()
    payload = client.get_event(event.id, include_open_close=True)
    if not payload: return 0
    status = payload.get("status", {})
    odds = payload.get("odds") or {}
    n_provider = grade_event_from_sgo(event, odds, status) if status.get("finalized") else 0
    n_computed = settle_event(event)
    return n_provider + n_computed
```

That's a *single* extra `/v2/events?eventID=` call per pending event — bounded by the count of stragglers (typically 0–10/night).

---

## 7. Implementation order

This plan is shippable as a single PR after [refactor-plan.md](refactor-plan.md) and [odds-system-plan.md](odds-system-plan.md) land:

1. Add `derive_event_scores`, `grade_from_sgo_odd`, `grade_event_from_sgo`, `_grade_ml/_grade_ml3way/_grade_spread/_apply_provider` to [settlement.py](../../core/event/odds/settlement.py).
2. Wire `derive_event_scores` into `Event.objects.upsert_from_payload` so `home_score`/`away_score`/`winner_code` populate.
3. Wire `grade_event_from_sgo` into `ingest_odds_sgo` (already required by odds-system-plan).
4. Add `reconcile_event_via_sgo` and call it from `settle_pending_events` for events whose `last_provider_refresh_at` is older than 4h.
5. Smoke-test against a captured `finalized=true` payload — verify a known game grades correctly across all categories.
6. Delete the SofaScore `winning`-flag path (`apply_provider_flag` retains the same signature; only its callers swap).

### Budget impact
0 additional SGO calls under normal operation. The reconcile helper costs at most one call per stuck event per night — negligible against the 2.5k object cap.

---

**Net effect:** the scope of the settlement refactor is tiny. The grader replaces ~20 lines of SofaScore-specific code with ~80 lines of SGO-specific code; everything below the grader (SettlementStatus enum, settle_event dispatcher, computed math, manual override, cron, REST exposure) is unchanged.
