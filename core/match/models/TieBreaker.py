"""Golden-total prediction storage (tie-cascade step 4).

Each player's prediction of the Golden Game's final combined score is
captured WITH their golden pick (``Game.objects.pick_on_locked_slot``) —
there is no separate submission window. ``NULL`` means "never picked the
golden", which the cascade treats as losing the prediction step.

The old chance-based winner methods (closest-total → random fallback) are
gone: matches never end in a draw and never use randomness — see
``MatchManager._resolve_winner`` for the full deterministic cascade.
"""

import uuid

from django.db import models

from core.abstract.models import AbstractManager, AbstractModel
from core.game.models import Game
from core.user.models import User


class TieBreakerManager(AbstractManager):

    def set_owner_total(self,tiebreaker,total):
        tiebreaker.owner_total=total
        tiebreaker.save()

    def set_player_2_total(self,tiebreaker,total):
        tiebreaker.player_2_total=total
        tiebreaker.save()

    def calculate_event_total(self, tiebreaker):
        event = tiebreaker.golden_game.event if tiebreaker.golden_game else None
        if event is None or event.home_score is None or event.away_score is None:
            return None
        tiebreaker.total = event.home_score + event.away_score
        tiebreaker.save(update_fields=["total"])
        return tiebreaker.total


class TieBreaker(AbstractModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    winner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='winner_tiebreaker', null=True, default=None)
    golden_game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='tiebreaker_golden_game', blank=False, null=True,
                                    default=None)

    # Actual combined final score of the golden event (cached by
    # ``calculate_event_total``); NULL until the event finalizes.
    total = models.IntegerField(null=True, blank=True, default=None)
    # Per-player predictions. NULL = that side never picked the golden
    # (predictions are mandatory at golden-pick time, so pick ⇔ prediction).
    owner_total = models.IntegerField(null=True, blank=True, default=None)
    player_2_total = models.IntegerField(null=True, blank=True, default=None)

    objects = TieBreakerManager()

    class meta:
        db_table = "'core.tiebreaker'"

    def __str__(self):
        if self.golden_game is None:
            return f'Tiebreaker {self.id} (no golden game)'
        match = self.golden_game.match
        return f'Tiebreaker for: {match.player_1} vs {match.player_2} '
