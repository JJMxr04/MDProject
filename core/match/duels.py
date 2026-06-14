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

from django.db.models import Q
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


# ---- duel page read helpers (phase 14 — duel hub) -------------------------
#
# The duel page (``duels_page_view``) needs three lists + a record. Duels are
# Matches (``match_type="duel"``); incoming challenges are still un-accepted
# Invites. Draw vs. in-progress is the one subtlety: both have ``winner=None``,
# so they are split on ``match_state == "completed"`` everywhere below.


def incoming_duel_invites(user):
    """Pending duel challenges addressed to ``user``, newest first.

    Only actionable rows: a match-type Invite still in ``sent`` state, flagged
    ``payload.duel``, not past its kickoff expiry. The expiry guard mirrors
    ``Invite.effective_state`` so the page never offers Accept on a kicked-off
    event (``accept_invite`` still raises ``InviteExpired`` as a backstop).
    ``payload__duel=True`` is a Postgres JSONField lookup — valid on this DB.
    """
    from core.mail.models import Invite

    now = timezone.now()
    return (
        Invite.objects.filter(
            player=user, type="match", state="sent", payload__duel=True,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .select_related("sender")
        .order_by("-invited_date")
    )


def outgoing_duel_invites(user):
    """Duel challenges ``user`` has sent that are still awaiting a response.

    Same shape as ``incoming_duel_invites`` but keyed on ``sender`` — pending
    (``state='sent'``), un-expired duel invites. These aren't Matches yet, so
    they live here until the opponent accepts (→ "In progress") or the kickoff
    passes. ``select_related('player')`` for the recipient's name/avatar.
    """
    from core.mail.models import Invite

    now = timezone.now()
    return (
        Invite.objects.filter(
            sender=user, type="match", state="sent", payload__duel=True,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .select_related("player")
        .order_by("-invited_date")
    )


def _duel_queryset(user):
    from core.match.models import Match

    return Match.objects.filter(match_type="duel").filter(
        Q(player_1=user) | Q(player_2=user)
    )


# Prefetch the bits ``duel_row`` reads so a 10-row page is a constant query
# count rather than one chain walk per duel.
_ROW_PREFETCH = (
    "games__event__home_team",
    "games__event__away_team",
    "games__bet__owner_outcome",
    "games__bet__player_2_outcome",
)


def accepted_duels(user):
    """The user's in-progress duels (accepted, awaiting the event result)."""
    return (
        _duel_queryset(user)
        .exclude(match_state="completed")
        .select_related("player_1", "player_2", "winner")
        .prefetch_related(*_ROW_PREFETCH)
        .order_by("-end_date")
    )


def finished_duels(user):
    """The user's settled duels (won/lost/draw), newest first."""
    return (
        _duel_queryset(user)
        .filter(match_state="completed")
        .select_related("player_1", "player_2", "winner")
        .prefetch_related(*_ROW_PREFETCH)
        .order_by("-end_date")
    )


def duel_record(user) -> dict:
    """Win/loss/draw/in-progress tallies for ``user``'s duels.

    ``won``  — completed, winner is the user.
    ``lost`` — completed, winner is the other player.
    ``draw`` — completed, no winner (push/void/postponed, D-14 #2).
    ``open`` — not yet completed (still ``accepted``).
    Draw and open both have ``winner=None`` — split on ``match_state``.
    """
    qs = _duel_queryset(user)
    completed = qs.filter(match_state="completed")
    won = completed.filter(winner=user).count()
    draw = completed.filter(winner__isnull=True).count()
    lost = completed.filter(winner__isnull=False).exclude(winner=user).count()
    decided = won + lost
    return {
        "total": qs.count(),
        "won": won,
        "lost": lost,
        "draw": draw,
        "open": qs.exclude(match_state="completed").count(),
        "win_rate": round(100 * won / decided) if decided else None,
    }


def duel_row(match, user) -> dict:
    """A single duel rendered from ``user``'s perspective.

    "Your side" comes off the one non-golden game's Bet: ``owner_outcome`` is
    the challenger's (player_1) Selection, ``player_2_outcome`` the opponent's.
    """
    is_p1 = match.player_1_id == user.id
    opponent = match.player_2 if is_p1 else match.player_1

    game = next(
        (g for g in match.games.all() if not g.is_golden),
        None,
    )
    bet = getattr(game, "bet", None) if game else None
    your_sel = opp_sel = None
    if bet is not None:
        your_sel = bet.owner_outcome if is_p1 else bet.player_2_outcome
        opp_sel = bet.player_2_outcome if is_p1 else bet.owner_outcome
    event = getattr(game, "event", None) if game else None

    if match.match_state != "completed":
        status = "open"
    elif match.winner_id is None:
        status = "draw"
    elif match.winner_id == user.id:
        status = "won"
    else:
        status = "lost"

    return {
        "id": str(match.id),
        "opponent_name": opponent.username if opponent else "—",
        "event_label": _event_label(event) if event else "",
        "your_side": your_sel.label if your_sel else "",
        "opponent_side": opp_sel.label if opp_sel else "",
        "status": status,  # won | lost | draw | open
        "kickoff": match.end_date,
    }
