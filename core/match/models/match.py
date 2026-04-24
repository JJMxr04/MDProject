import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone
from rest_framework.response import Response

from core.abstract.models import AbstractManager, AbstractModel
from core.game.models import Game, PickError
from core.mail.models import Emails
from core.match.models.TieBreaker import TieBreaker
from core.match.scoring import score_match
from core.user.models import User


REGULAR_GAMES_PER_PLAYER = 5


class MatchManager(AbstractManager):
    def create_match(self, player_1, player_2=None, start_date=None, match_type="public"):
        start_date = timezone.now()
        end_date = start_date + timedelta(weeks=1)
        if player_2 is None:
            return self.create(
                player_1=player_1,
                player_2=player_2,
                start_date=start_date,
                end_date=end_date,
                match_type="public",
            )
        match = self.create(
            player_1=player_1,
            player_2=player_2,
            start_date=start_date,
            end_date=end_date,
            match_type="private",
        )
        return self.accept_match(match, player_2)

    def accept_match(self, match, player_2):
        match = self.get_object_by_id(id=match.id)
        if match is None:
            return None
        if match.player_1 == player_2:
            return None
        match.match_state = "accepted"
        match.player_2 = player_2
        match.end_date = timezone.now() + timedelta(days=7)

        for slot in range(1, REGULAR_GAMES_PER_PLAYER + 1):
            Game.objects.create_game(
                match=match, owner=match.player_1, player_2=match.player_2, slot=slot
            )
            Game.objects.create_game(
                match=match, owner=match.player_2, player_2=match.player_1, slot=slot
            )

        golden_game = Game.objects.get_golden_game(match.player_1, match.player_2, match)
        match.tiebreaker = TieBreaker.objects.create(golden_game=golden_game)
        match.save()
        return match

    def upload_pick(self, player, match, data):
        try:
            Game.objects.upload_pick(
                current_user=player,
                match=match,
                event_id=data.get("event_id"),
                selection_id=data.get("player_choice"),
            )
            return Response({"message": "Request was successful"}, status=200)
        except PickError as exc:
            return Response({"error": str(exc)}, status=400)

    def maybe_complete_match(self, match):
        """If the match is decided (every slot scored or window closed),
        finalize it. Idempotent — re-entry on already-completed matches is a
        no-op."""
        if match.match_state == "completed":
            return
        _, _, decided = score_match(match)
        window_closed = bool(match.end_date and match.end_date <= timezone.now())
        if not decided and not window_closed:
            return
        self.calculate_winner(match)

    def calculate_winner(self, match):
        p1_score, p2_score, _ = score_match(match)
        if p1_score > p2_score:
            match.winner = match.player_1
        elif p2_score > p1_score:
            match.winner = match.player_2
        else:
            match.winner = TieBreaker.objects.calculate_winner(match.tiebreaker)
        match.match_state = "completed"
        match.save(update_fields=["winner", "match_state"])

        if match.winner == match.player_1:
            Emails.send_match_victory_notification(match.player_1, match.player_2.username)
            Emails.send_match_lost_notification(match.player_2, match.player_1.username)
        elif match.winner == match.player_2:
            Emails.send_match_victory_notification(match.player_2, match.player_1.username)
            Emails.send_match_lost_notification(match.player_1, match.player_2.username)


class Match(AbstractModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    player_1 = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="player_1_match"
    )
    player_2 = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="player_2_match",
        null=True,
        default=None,
    )
    winner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="winner_match",
        null=True,
        default=None,
        blank=True,
    )

    match_state = models.CharField(max_length=10, default="created")
    match_type = models.CharField(max_length=10, default="public")

    tiebreaker = models.ForeignKey(
        TieBreaker,
        on_delete=models.CASCADE,
        related_name="match_tiebreaker",
        null=True,
        blank=True,
        default=None,
    )

    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True, default=None)

    objects = MatchManager()

    class Meta:
        db_table = "core.match"

    def __str__(self):
        return f"{self.player_1} vs {self.player_2} "

    @property
    def player_1_score(self):
        return score_match(self)[0]

    @property
    def player_2_score(self):
        return score_match(self)[1]

    @property
    def fully_decided(self):
        return score_match(self)[2]

    @property
    def golden_game(self):
        return self.games.filter(is_golden=True).first()

    def regular_games_for(self, user):
        return self.games.filter(owner=user, is_golden=False).order_by("slot")
