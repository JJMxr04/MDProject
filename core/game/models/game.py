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

        try:
            event_pk = int(event_id)
        except (TypeError, ValueError):
            raise PickError("Invalid event_id")
        try:
            selection_pk = int(selection_id)
        except (TypeError, ValueError):
            raise PickError("Invalid selection_id")

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

    def get_golden_game(self, player_1, player_2, match):
        now = timezone.now()
        window_start = now + timedelta(days=5)
        window_end = now + timedelta(days=7)
        event = (
            Event.objects.filter(
                completed=False,
                start_time__range=(window_start, window_end),
            )
            .order_by("?")
            .first()
        )
        bet_market = None
        if event is not None:
            markets = list(
                Market.objects.filter(
                    event=event, category="MONEYLINE", scope="FULL_GAME"
                )
            )
            bet_market = random.choice(markets) if markets else None

        game = self.create_game(
            match=match,
            owner=player_1,
            player_2=player_2,
            slot=0,
            is_golden=True,
            event=event,
        )
        if bet_market is not None:
            # Pre-seed with a default selection (HOME) so the slot displays
            # something on the UI before either player makes a pick. This is
            # only auto-data; either player can still override via upload_pick.
            home_selection = bet_market.selections.filter(type="HOME").first()
            if home_selection is not None:
                Bet.objects.set_owner_outcome(game.bet, home_selection)
        return game


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
        owner_done = (
            self.bet.owner_outcome is not None
            and self.bet.owner_outcome.settlement_status != "PENDING"
        )
        player_2_done = (
            self.bet.player_2_outcome is not None
            and self.bet.player_2_outcome.settlement_status != "PENDING"
        )
        return owner_done and player_2_done
