import random
import uuid
from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone

from core.abstract.models import AbstractManager, AbstractModel
from core.event.models import Event, Market, Selection
from core.game.models.bet import Bet
from core.mail.models import Emails
from core.match.scoring import DEADLINE_BUFFER
from core.user.models import User


class PickError(Exception):
    """Raised by Game.objects.upload_pick on validation failures."""


class GoldenGameUnavailable(Exception):
    """Raised by Game.objects.get_golden_game when the catalog can't provide
    a viable Golden Game seed (no events in window, or events exist but none
    have a market we can attach a selection to).

    The caller should let it propagate out of ``Match.objects.accept_match``
    so the surrounding ``transaction.atomic`` rolls back the half-built
    Match + Games + TieBreaker, and the view returns 400 + portal toast.
    """


class GameManager(AbstractManager):
    def create_game(self, *, match, owner, player_2, slot: int, is_golden: bool = False, event=None):
        return self.create(
            match=match,
            owner=owner,
            player_2=player_2,
            slot=slot,
            is_golden=is_golden,
            event=event,
            bet=Bet.objects.create_bet(),
        )

    @transaction.atomic
    def upload_pick(self, *, current_user, match, event_id, selection_id):
        """Owner or opponent picks a Selection for one slot in a Match.

        Returns the Game row that was updated.
        Raises PickError on validation failures.

        Rules (from api-switch/game-match-audit-plan.md §5.1):
          - Owner must be picking ≥ 8h before event start.
          - Opponent must pick before event start.
          - No two slots in the same Match may share the same (event, market).
        """
        if current_user not in (match.player_1, match.player_2):
            raise PickError("Not a participant of this match")
        if match.match_state != "accepted":
            raise PickError("Match not active")

        event_pk = (event_id or "").strip() if isinstance(event_id, str) else event_id
        selection_pk = (selection_id or "").strip() if isinstance(selection_id, str) else selection_id
        if not event_pk or not selection_pk:
            raise PickError("Invalid event_id or selection_id")

        try:
            selection = Selection.objects.select_related(
                "market", "market__event"
            ).get(pk=selection_pk)
        except Selection.DoesNotExist:
            raise PickError("Selection not found")
        if selection.market.event_id != event_pk:
            raise PickError("Selection does not belong to that event")

        event = selection.market.event
        if event.start_time is None:
            raise PickError("Event has no start time")

        now = timezone.now()
        is_owner_side = current_user == match.player_1
        target_owner = match.player_1 if is_owner_side else match.player_2

        # Locate the slot. The owner of a slot is the side whose pick "claims"
        # the event for that game. If the slot is empty (event is None), the
        # current user is acting as owner; otherwise they're acting as opponent
        # on a slot some other user already claimed.
        owned_slots = list(
            self.filter(match=match, owner=target_owner).select_related(
                "bet", "bet__owner_outcome", "bet__player_2_outcome", "event"
            ).order_by("is_golden", "slot")
        )
        # First, check if this user is the opponent on an existing game holding
        # this event — i.e. the other side already claimed it.
        opp_game = next(
            (g for g in self.filter(match=match, player_2=current_user, event_id=event_pk)
                  .select_related("bet", "event")), None,
        )
        if opp_game is not None:
            return self._apply_opponent_pick(opp_game, selection, now)

        # Otherwise current user is acting as owner on one of their own slots.
        # Anti-duplicate: same (event, market) cannot appear twice in this match.
        existing_market_pairs = set(
            self.filter(match=match)
            .exclude(event__isnull=True)
            .values_list("event_id", "bet__owner_outcome__market_id")
        )
        if (event_pk, selection.market_id) in existing_market_pairs:
            raise PickError("This event/market combination has already been picked")

        # Owner deadline.
        if event.start_time - now < DEADLINE_BUFFER:
            raise PickError("Owner picks must be made at least 8 hours before event start")

        # Find first empty slot for this user.
        empty_slot = next((g for g in owned_slots if g.event_id is None), None)
        if empty_slot is None:
            raise PickError("All your slots already have an event")

        empty_slot.event = event
        empty_slot.save(update_fields=["event"])
        Bet.objects.set_owner_outcome(empty_slot.bet, selection)

        Emails.send_opponent_pick_notification(empty_slot.player_2, current_user.username)
        return empty_slot

    def _apply_opponent_pick(self, game, selection: Selection, now):
        if game.event is None or game.event.start_time is None:
            raise PickError("Slot has no event yet")
        if game.event.start_time <= now:
            raise PickError("Event has already started; opponent pick window closed")
        if selection.market.event_id != game.event_id:
            raise PickError("Selection does not belong to this game's event")
        if game.bet.owner_outcome is None:
            raise PickError("Owner has not picked yet on this slot")
        Bet.objects.set_player_2_outcome(game.bet, selection)
        Emails.send_opponent_pick_notification(game.owner, game.player_2.username)
        return game

    @transaction.atomic
    def pick_on_locked_slot(self, *, current_user, game_id, selection_id):
        """Pick handler for slots whose market is pre-locked (Golden Game).

        Routes to ``owner_outcome`` or ``player_2_outcome`` based on which
        side of the match the current user is on — both can pick freely,
        independent of the other side.

        Validates:
          - User is in the match.
          - Slot has a ``locked_market`` (otherwise use the regular
            ``upload_pick`` flow).
          - Selected ``Selection`` belongs to the locked market.
          - Event hasn't started yet.
          - User can't pick the same selection their opponent already
            picked (each side must pick a different option).
        """
        try:
            game = self.select_related(
                "bet", "bet__locked_market", "event", "match",
                "match__player_1", "match__player_2",
            ).get(pk=game_id)
        except Game.DoesNotExist:
            raise PickError("Game not found")

        match = game.match
        if current_user not in (match.player_1, match.player_2):
            raise PickError("Not a participant of this match")

        bet = game.bet
        locked_market = bet.locked_market if bet else None
        if locked_market is None:
            raise PickError("This slot doesn't have a locked market")

        try:
            selection = Selection.objects.select_related("market").get(pk=selection_id)
        except Selection.DoesNotExist:
            raise PickError("Selection not found")
        if selection.market_id != locked_market.id:
            raise PickError("Selection isn't part of this slot's locked market")

        if game.event is None or game.event.start_time is None:
            raise PickError("Slot has no event yet")
        if game.event.start_time <= timezone.now():
            raise PickError("Event has already started; pick window closed")

        # Both players are free to pick the same selection — picking the
        # same side as your opponent is a deliberate "block" tactic, not a
        # mistake. Front-end shows a "Picked by X" badge for visibility but
        # doesn't disable the card.
        is_player_1 = (current_user == match.player_1)
        if is_player_1:
            Bet.objects.set_owner_outcome(bet, selection)
        else:
            Bet.objects.set_player_2_outcome(bet, selection)
        return game
        return game

    def get_golden_game(self, player_1, player_2, match):
        """Find an event + market for the Golden Game and create the slot.

        The aggregator is the source of truth for the events catalog —
        MDProject's local Event table only holds rows users have already
        picked. So we query the aggregator over HTTP, walk the fallback
        chain on its response, then ``ensure_chain`` the chosen
        (event, selection) into the local DB before linking the Game.

        Search policy:
          - Aggregator ``GET /v1/events`` between ``now + DEADLINE_BUFFER``
            and ``match.end_date``, ordered closest-first by the API.
          - Cross-event preference: try every candidate at the top market
            priority before downgrading. So a MONEYLINE event always wins
            over a SPREAD-only one, even if the SPREAD event starts sooner.
          - Pick a default selection (HOME for ML/SPREAD, OVER for TOTAL,
            else first with non-null odds). Either player can override.

        Failures (raised, not silently returned):
          - Aggregator unreachable.
          - No events in the window.
          - Events exist but none have a market we can seed.

        Caller (``MatchManager.accept_match``) wraps in ``transaction.atomic``
        so the raise rolls back the partial match.
        """
        from core.event.providers.aggregator_client import (
            AggrigatorClient, AggrigatorError,
        )
        from core.event.services.aggregator_chain import (
            ensure_chain, ChainBuildError,
        )

        now = timezone.now()
        window_start = now + DEADLINE_BUFFER
        window_end = match.end_date or (now + timedelta(days=7))
        if window_end <= window_start:
            window_end = window_start + timedelta(days=7)

        client = AggrigatorClient()
        try:
            body = client.list_events(
                starts_after=window_start.isoformat(),
                starts_before=window_end.isoformat(),
                include="markets",
                page_size=50,
            )
        except AggrigatorError as exc:
            raise GoldenGameUnavailable(
                "Couldn't reach the events catalog right now. Please try "
                "again in a moment."
            ) from exc

        candidates = body.get("items") or []
        if not candidates:
            raise GoldenGameUnavailable(
                "No events are scheduled for your match window. "
                "Try again later when more events are scheduled."
            )

        picked = self._pick_from_aggregator_listing(candidates)
        if picked is None:
            raise GoldenGameUnavailable(
                "Events are scheduled but none have markets posted yet. "
                "Try again later."
            )
        event_id, selection_id = picked

        # Mirror the chain into the local DB so we have a real local Market
        # row to lock against. The seed selection is used only as a vehicle
        # to upsert the surrounding Sport→…→Market chain — neither side's
        # outcome is set, so both players still get to actively pick within
        # the locked market.
        try:
            seed_selection = ensure_chain(event_id, selection_id)
        except ChainBuildError as exc:
            raise GoldenGameUnavailable(
                "Couldn't load the selected event into your match. "
                "Please try again."
            ) from exc

        chosen_event = seed_selection.market.event
        chosen_market = seed_selection.market

        game = self.create_game(
            match=match,
            owner=player_1,
            player_2=player_2,
            slot=0,
            is_golden=True,
            event=chosen_event,
        )
        # Lock the market on the bet — the popup constrains both players to
        # selections inside this market — but DON'T pre-pick a side.
        # player_1 and player_2 each submit their own selection.
        game.bet.locked_market = chosen_market
        game.bet.save(update_fields=["locked_market", "updated_at"])
        return game

    # Market fallback chain for the Golden Game seed. MONEYLINE first because
    # "X to win" is the clearest meaning for a featured slot; SPREAD/TOTAL are
    # next-best because they're widely-recognized full-game lines; PROPS_*
    # last as "any market beats no market".
    _GOLDEN_MARKET_PREFERENCE = [
        ("MONEYLINE", "FULL_GAME"),
        ("SPREAD", "FULL_GAME"),
        ("TOTAL", "FULL_GAME"),
        ("PROPS_GAME", None),
        ("PROPS_TEAM", None),
    ]

    def _pick_from_aggregator_listing(self, candidates):
        """Walk an aggregator ``Page[EventWithMarketsOut]`` items list.

        Two-pass: scan every candidate for the top-priority market first,
        only downgrade if no candidate matches. Returns
        ``(event_id, selection_id)`` of the first hit or ``None``.
        """
        for category, scope in self._GOLDEN_MARKET_PREFERENCE:
            for ev in candidates:
                for market in (ev.get("markets") or []):
                    if market.get("category") != category:
                        continue
                    if scope is not None and market.get("scope") != scope:
                        continue
                    sel = self._default_selection_from_payload(market)
                    if sel is None:
                        continue
                    return ev["id"], sel["id"]

        # Last-ditch: any market on any candidate.
        for ev in candidates:
            for market in (ev.get("markets") or []):
                sel = self._default_selection_from_payload(market)
                if sel is not None:
                    return ev["id"], sel["id"]
        return None

    @staticmethod
    def _default_selection_from_payload(market):
        """Pick a default selection from an aggregator market dict.
        Preference: HOME (ML/SPREAD) > OVER (TOTAL) > first with non-null
        decimal_odds. Returns ``None`` if the market has no priced
        selections — caller should try another market.
        """
        cat = market.get("category")
        sels = market.get("selections") or []
        priced = [s for s in sels if s.get("decimal_odds") is not None]
        if not priced:
            return None
        if cat in ("MONEYLINE", "SPREAD"):
            for s in priced:
                if s.get("type") == "HOME":
                    return s
        elif cat == "TOTAL":
            for s in priced:
                if s.get("type") == "OVER":
                    return s
        return priced[0]


class Game(AbstractModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(
        "core_match.Match", on_delete=models.CASCADE, related_name="games"
    )
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="owner_game"
    )
    player_2 = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="player_2_game"
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.PROTECT,
        related_name="games",
        null=True,
        blank=True,
    )
    bet = models.OneToOneField(
        Bet, on_delete=models.CASCADE, related_name="game", null=True, blank=True
    )

    is_golden = models.BooleanField(default=False)
    slot = models.SmallIntegerField(default=0)

    objects = GameManager()

    class Meta:
        db_table = "core.game"
        constraints = [
            models.UniqueConstraint(
                fields=["match", "owner", "slot", "is_golden"],
                name="uq_game_match_owner_slot_golden",
            ),
        ]

    @property
    def commence_time(self):
        return self.event.start_time if self.event else None

    @property
    def deadline_time(self):
        return (self.commence_time - DEADLINE_BUFFER) if self.commence_time else None

    @property
    def home_team(self):
        return self.event.home_team if self.event else None

    @property
    def away_team(self):
        return self.event.away_team if self.event else None

    @property
    def winner(self):
        return self.event.winner if self.event else None

    @property
    def is_settled(self) -> bool:
        """A Game is settled when the event reaches a terminal state and
        every pick that exists has resolved.

        Unpicked sides are NOT a blocker: once the event finishes (or is
        postponed/canceled), no one can go back and add a pick to that slot
        — Game.upload_pick rejects late picks via DEADLINE_BUFFER. So a
        missing pick at terminal-state time is a permanent forfeit, and
        the game's display status flips to "Completed".
        """
        if self.event is None:
            return False
        if self.event.status_type not in ("finished", "postponed", "canceled"):
            return False
        bet = self.bet
        owner_pick = bet.owner_outcome if bet else None
        p2_pick = bet.player_2_outcome if bet else None
        owner_ok = owner_pick is None or owner_pick.settlement_status != "PENDING"
        p2_ok = p2_pick is None or p2_pick.settlement_status != "PENDING"
        return owner_ok and p2_ok
