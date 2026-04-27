# Game / Match Audit — SportsGameOdds Edition

**Goal:** confirm the existing Game/Match refactor (shipped from [sofa game-match-audit-plan.md](../sofa/game-match-audit-plan.md)) survives the SGO migration, and call out the only places it needs touching.

**TL;DR:** the refactor was provider-agnostic by design. `Bet.owner_outcome` is a FK to `Selection`; scoring reads `Selection.settlement_status`. None of that depends on SofaScore. The only impact of switching providers is **a FK type change** (BigInt → CharField) flowing through Bet → Selection.

This is a **delta plan**. Everything not called out here stays exactly as today.

---

## 0. Audit summary — what's still good

| Layer | Status under SGO | Why |
|---|---|---|
| `core/match/scoring.py` | ✅ no changes | Reads `Selection.settlement_status` enum, provider-agnostic |
| `Match` model (no game FKs, no completion booleans) | ✅ no changes | The 11 caches stayed gone |
| `Game` model (FK `match`, `is_golden`, `slot`, derived properties) | ✅ no changes | All snapshot fields stayed dropped |
| `Bet` (no settlement booleans, snapshot odds, picked_at) | ⚠️ FK type change only | `owner_outcome` and `player_2_outcome` still point to `Selection`; only the underlying PK type changes |
| `Game.objects.upload_pick` | ⚠️ one validation tweak | `event_id` becomes a string (was BigInt under the SofaScore-era PK) |
| `core/game/events.py::reopen_games_for_voided_event` | ✅ no changes | Same trigger condition (`status_type in ('canceled','postponed')`) |
| Event-finished hook / `_should_settle` | ✅ no changes | Status-driven, not provider-driven |
| Selection-post-save signal that re-scores affected matches | ✅ no changes | Reads only Selection rows |
| Tiebreaker math (`calculate_event_total`) | ✅ no changes | Still reads `event.home_score / away_score`, just populated by [settlement-plan.md §3.1](settlement-plan.md) instead of by SofaScore |

---

## 1. The one breaking change — Selection PK becomes a string

Today `Selection.id = BigIntegerField(primary_key=True)` (SofaScore's `sourceId`).

Under SGO ([odds-system-plan.md §5](odds-system-plan.md)) it becomes:
```python
Selection.id = CharField(max_length=128, primary_key=True)
# Synthesized as: f"{market.id}:{statEntityID}-{sideID}"
```

This affects two FK fields on `Bet`:
- `Bet.owner_outcome` → `Selection`
- `Bet.player_2_outcome` → `Selection`

Both currently `BigIntegerField` (because Django mirrors the FK target type).

### What needs to happen
- One migration swaps the FK column types from BigInt to CharField(128).
- Dev DB wipe is acceptable per the existing precedent ([sofa refactor-plan §5](../sofa/refactor-plan.md)). All bets in dev are throwaway; prod isn't running this stack.
- No callsites in [bet.py](../../core/game/models/bet.py), [game.py](../../core/game/models/game.py), or scoring read the PK type — all Selection reads go through the FK relation, not the integer ID.

That's the entire impact. No rewrite of `BetManager`, no rewrite of `Game.objects.upload_pick`'s pick-resolution chain.

---

## 2. `event_id` is now a string in `upload_pick`

The §1.1 fix in the sofa plan converted `uuid.UUID(data["event_id"])` to `int(data["event_id"])`. With SGO, `Event.id` is a string like `mXCZTRJnbX8ib64z1h3D`, so the validation simplifies further:

```python
# core/match/models/match.py — was:
try:
    candidate_event_id = int(data.get("event_id"))
except (TypeError, ValueError):
    return Response({"error": "Invalid event_id"}, status=400)

# Becomes:
candidate_event_id = (data.get("event_id") or "").strip()
if not candidate_event_id or len(candidate_event_id) > 32:
    return Response({"error": "Invalid event_id"}, status=400)
```

And in [Game.objects.upload_pick](../../core/game/models/game.py):

```python
# Was:
selection = Selection.objects.select_related("market", "market__event").get(pk=int(selection_id))

# Becomes:
selection = Selection.objects.select_related("market", "market__event").get(pk=selection_id)
```

No int coercion. `selection_id` is already a string.

---

## 3. Anti-duplicate check — still per (event, market)

The sofa plan locked in: same event + same market is rejected; same event + different market is allowed (so e.g. owner picks ML and opponent picks the total — still one slot, both bets valid).

That logic operates on `(bet.owner_outcome.market.event_id, bet.owner_outcome.market_id)` tuples. **No change** — the comparison still works regardless of whether IDs are ints or strings.

---

## 4. Snapshot odds at pick — minor format note

`Bet.owner_decimal_odds_at_pick` is a `DecimalField(max_digits=8, decimal_places=4)`. SGO returns American format, but [odds-system-plan.md §5.1](odds-system-plan.md) defines `american_to_decimal` and the converter runs at ingest. By the time `upload_pick` reads `selection.decimal_odds`, it's already a `Decimal` — exactly the type the snapshot field expects.

No change to the `Bet` model.

---

## 5. Tiebreaker — no change but worth verifying

[TieBreaker.calculate_event_total](../../core/match/models/TieBreaker.py) reads `event.home_score + event.away_score`. The sofa fix bound those to `event.home_score` / `event.away_score` IntegerFields. Under SGO, these populate from the canonical-stat odd's `score` field via [settlement-plan.md §3.1](settlement-plan.md):

```python
event.home_score = odds["points-home-game-ml-home"]["score"]   # NFL example
event.away_score = odds["points-away-game-ml-away"]["score"]
```

So tiebreaker math works unchanged. Only smoke-test verification needed: pull a finalized golden-game event and confirm both scores land before tiebreaker runs.

---

## 6. The pre-flight checklist

Before the SGO migration ships, walk through these to confirm nothing regresses:

- [ ] `Bet.owner_outcome` migration swap from BigInt FK to CharField FK runs cleanly on dev.
- [ ] `Game.objects.upload_pick` accepts a string `event_id` and a string `selection_id`.
- [ ] A test pick → settle → score → match-complete walk produces the right `Match.player_1_score` / `player_2_score`.
- [ ] Voided event triggers `reopen_games_for_voided_event` and clears the right Bets.
- [ ] Tiebreaker math still works (golden game finalizes, `event.home_score + event.away_score` is non-null).
- [ ] No template references to old field names regress (the sofa plan flagged [my_match_detail.html](../../core/match/templates/portal/match/my_match_detail.html) — still tracked as out of scope).

---

## 7. What this plan deliberately does **not** do

- Re-litigate the Game/Match refactor. That ship has sailed; the model is sound under either provider.
- Touch the Bet booleans / `_settle` chain. Already deleted in the sofa pass.
- Add provider-aware fields to `Bet`. The bet doesn't care which provider settled the underlying selection — `settlement_status` on the Selection is the only signal scoring needs.
- Re-design tiebreaker. The current shape works as long as `home_score` / `away_score` populate, and SGO populates them.

---

## 8. Implementation cost

A single migration + 2 small file edits:

1. `core/game/migrations/0004_bet_outcome_pk_type.py` — `AlterField` on `Bet.owner_outcome` and `Bet.player_2_outcome` to CharField FK. (May need to be split into `RemoveField` + `AddField` since Django can't always alter FK column types in place.)
2. [core/match/models/match.py](../../core/match/models/match.py) — drop the `int(...)` coercion on `event_id`; relax to string-shape check.
3. [core/game/models/game.py](../../core/game/models/game.py) — drop the `int(selection_id)` coercion in `upload_pick`.

Smoke test, ship, done. The Game/Match refactor was correctly designed to be provider-independent; the SGO migration validates that.
