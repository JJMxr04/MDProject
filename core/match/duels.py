"""Duels — single-game, opposite-side challenges (phase 14).

The smallest PvP unit: one game, two players, opposite sides, settles when the
event ends. The challenger picks an event *and* an outcome up front; accepting
puts the opponent on the other side automatically — no pick phase.

D-14 decisions baked in here:
  1. "Opposite" must be unambiguous → v1 restricts duels to markets with
     exactly two priced selections (TOTAL over/under, SPREAD home/away, two-way
     MONEYLINE). Soccer 3-way moneyline is excluded.
  2. Push / void / postponed settles as a draw (handled at settlement, in
     ``MatchManager``).
  3. The challenge locks at send and the invite expires at kickoff
     (``expires_at = event.start_time``) — no owner-side 8h buffer, because the
     responder's side is deterministic.
  4. Ladder-exempt (no rating delta) — duels feed head-to-head history only.
"""

from __future__ import annotations

from django.utils import timezone

from core.event.models import Selection


class DuelError(Exception):
    """User-facing duel validation failure — views surface the message verbatim."""


def _priced_selections(market):
    return list(market.selections.filter(decimal_odds__isnull=False))


def opposite_selection(selection: Selection) -> Selection:
    """The other priced selection in ``selection``'s market.

    Enforces D-14 #1: the market must have exactly two priced selections, and
    the chosen one must be among them. Raises ``DuelError`` otherwise — the
    message is shown to the challenger.
    """
    market = selection.market
    priced = _priced_selections(market)
    if len(priced) != 2:
        raise DuelError(
            "Duels need a market with exactly two priced outcomes — like "
            "over/under, a point spread, or a two-way moneyline. Pick one of "
            "those and try again."
        )
    others = [s for s in priced if s.id != selection.id]
    if len(others) != 1:
        raise DuelError("That outcome can't be dueled — choose a two-way market.")
    return others[0]


def send_duel(challenger, opponent, event_id: str, selection_id: str):
    """Validate and send a duel challenge from ``challenger`` to ``opponent``.

    Steps (all before any write that the recipient sees):
      - ``ensure_chain`` mirrors the (event, selection) into the local DB so the
        Event chain exists before the invite is even accepted (same pattern the
        Golden Game uses at accept time).
      - the event must be in the future (you can't duel a game that kicked off),
      - the market must be two-way (D-14 #1),
      - the opponent must be a friend (v1 — email-invitee duels can come later).

    Returns the created ``Invite`` (type ``match``, ``payload.duel = True``,
    ``expires_at = event.start_time``).
    """
    from core.event.services.aggregator_chain import ChainBuildError, ensure_chain
    from core.mail.models import Invite
    from core.metrics.models import track

    if opponent == challenger:
        raise DuelError("You can't duel yourself.")
    if not challenger.is_friend(opponent):
        raise DuelError("You can only duel your friends right now.")

    try:
        # mirror_full_market: duels need the market's opposite side locally so
        # ``opposite_selection`` can resolve it (D-14 #1).
        selection = ensure_chain(event_id, selection_id, mirror_full_market=True)
    except ChainBuildError as exc:
        raise DuelError("Couldn't load that event — please try again.") from exc

    event = selection.market.event
    if not event.start_time or event.start_time <= timezone.now():
        raise DuelError("That game has already started — pick an upcoming event.")

    opposite = opposite_selection(selection)

    payload = {
        "duel": True,
        "event_id": event.id,
        "selection_id": selection.id,
        "opposite_selection_id": opposite.id,
        # Display strings captured at send so the invite card renders without
        # re-querying the chain (labels are stable; odds may drift but the
        # sides don't — no money is staked, D-14 #3).
        "event_label": _event_label(event),
        "challenger_label": (selection.label or selection.type or "")[:128],
        "opponent_label": (opposite.label or opposite.type or "")[:128],
        "kickoff": event.start_time.isoformat(),
    }

    invite = Invite.objects.create_invite(
        obj_id=None,
        player=opponent,
        invite_type="match",
        sender=challenger,
        payload=payload,
        expires_at=event.start_time,  # D-14 #3: accept allowed up to kickoff
    )
    track(challenger, "duel_sent", invite_id=str(invite.pk), event_id=event.id)
    return invite


def _event_label(event) -> str:
    home = getattr(event, "home_team", None)
    away = getattr(event, "away_team", None)
    if home and away:
        return f"{away} @ {home}"[:128]
    return str(event)[:128]
