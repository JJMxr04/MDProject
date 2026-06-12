import uuid
from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone

from core.abstract.models import AbstractManager, AbstractModel
from core.game.models import Game, PickError
from core.game.models.game import GoldenGameUnavailable
from core.mail.models import Emails
from core.match import formats
from core.match.models.TieBreaker import TieBreaker
from core.match.scoring import golden_winner_side, score_match, winning_odds_totals
from core.user.models import User


class MatchManager(AbstractManager):
    def create_match(self, player_1, player_2=None, start_date=None,
                     match_type="public", match_format=None):
        """Create a match in the given format (BLITZ/CLASSIC/MARATHON —
        D-5 #4: fixed at creation, no renegotiation).

        Raises ``FixtureUnavailable`` when the format's window holds fewer
        distinct pickable events than the format needs (D-5 #2), and
        ``GoldenGameUnavailable`` when the Golden Game can't seed — either
        way nothing is written.

        Public (``player_2=None``): pre-create gates only.
        Private: the whole create+accept runs in one transaction, so a
        raise from ``accept_match`` rolls the Match row back too
        (previously it leaked a stray ``created`` match).
        """
        match_format = formats.normalize_format(match_format)
        start_date = timezone.now()
        end_date = start_date + formats.format_window(match_format)
        from core.metrics.models import track

        # Fixture-availability gate (D-5 #2) — applies to both branches.
        Game.objects.assert_window_viable(
            match_format=match_format, window_end=end_date,
        )

        if player_2 is None:
            Game.objects.find_golden_candidate(window_end=end_date)
            match = self.create(
                player_1=player_1,
                player_2=player_2,
                start_date=start_date,
                end_date=end_date,
                match_type="public",
                format=match_format,
            )
            track(player_1, "match_created", match_id=str(match.id),
                  match_type="public", format=match_format)
            return match
        with transaction.atomic():
            match = self.create(
                player_1=player_1,
                player_2=player_2,
                start_date=start_date,
                end_date=end_date,
                match_type="private",
                format=match_format,
            )
            track(player_1, "match_created", match_id=str(match.id),
                  match_type="private", format=match_format)
            return self.accept_match(match, player_2)

    @transaction.atomic
    def accept_match(self, match, player_2):
        """Accept a match and pre-create all Game slots + Golden Game seed.

        The whole flow is atomic — if ``Game.objects.get_golden_game`` raises
        ``GoldenGameUnavailable`` (no events, or no markets we can seed
        against), every Match/Game/TieBreaker write here rolls back and the
        exception propagates to the caller. Callers (invite-accept,
        public-match-accept, viewsets) translate that into a 400 + portal
        toast — never leaves a half-built match in the DB.
        """
        match = self.get_object_by_id(id=match.id)
        if match is None:
            return None
        if match.player_1 == player_2:
            return None
        match.match_state = "accepted"
        match.player_2 = player_2
        # The window restarts at accept — its length comes from the format
        # fixed at creation (D-5 #4).
        match.end_date = timezone.now() + formats.format_window(match.format)

        for slot in range(1, match.games_per_player + 1):
            Game.objects.create_game(
                match=match, owner=match.player_1, player_2=match.player_2, slot=slot
            )
            Game.objects.create_game(
                match=match, owner=match.player_2, player_2=match.player_1, slot=slot
            )

        # May raise GoldenGameUnavailable — the @transaction.atomic decorator
        # rolls back every write above on raise.
        golden_game = Game.objects.get_golden_game(match)
        match.tiebreaker = TieBreaker.objects.create(golden_game=golden_game)
        match.save()

        from core.metrics.models import track
        track(player_2, "match_accepted", match_id=str(match.id))
        return match

    def upload_pick(self, player, match, data):
        """Thin pass-through to ``Game.objects.upload_pick`` — returns the
        linked ``Game`` and lets ``PickError`` propagate to the view.

        (Previously wrapped the call in try/except PickError → DRF Response,
        which silently turned every validation failure into a 200 success
        when the caller — a plain Django view — discarded the Response.)
        """
        return Game.objects.upload_pick(
            current_user=player,
            match=match,
            event_id=data.get("event_id"),
            selection_id=data.get("player_choice"),
        )

    def maybe_complete_match(self, match):
        """If the match is decided (every slot scored or window closed),
        finalize it. Idempotent — re-entry on already-completed matches is a
        no-op.

        Settlement webhooks can deliver concurrently (and the cron can race
        a webhook), so finalization runs under a row lock with a state
        re-check: only the caller that wins the lock sees ``match_state !=
        "completed"`` and sends the result emails.
        """
        if match.match_state == "completed":
            return
        _, _, decided = score_match(match)
        window_closed = bool(match.end_date and match.end_date <= timezone.now())
        if not decided and not window_closed:
            return
        with transaction.atomic():
            # No select_related here: player_2/tiebreaker are nullable FKs
            # and FOR UPDATE can't lock the outer side of a LEFT JOIN.
            locked = self.select_for_update().get(pk=match.pk)
            if locked.match_state == "completed":
                return
            self.calculate_winner(locked)

    def calculate_winner(self, match):
        """Finalize the match — matches NEVER end in a draw (real-money
        constraint; only Duels may draw, for postponed events).

        Deterministic tie cascade, every step skill-based and auditable:
          1. Regular-pick points.
          2. Golden Game pick (zero-sum picks, so at most one side hits).
          3. Sum of decimal odds across winning picks — bolder correct
             picks beat safe ones.
          4. Golden-total prediction (captured WITH the golden pick):
             closest to the actual total; equidistant → under beats over;
             only one side predicted → they win.
          5. Last resort (neither side ever picked the golden): the
             accepter (player_2) wins — known upfront, the match creator
             can never farm a dead heat.
        """
        match.winner = self._resolve_winner(match)
        match.match_state = "completed"
        match.save(update_fields=["winner", "match_state"])

        # dedupe_key guards the email layer independently of the row lock
        # above — a queued result email for this (match, recipient) makes
        # any duplicate defer a no-op.
        if match.winner == match.player_1 and match.player_2 is not None:
            Emails.send_match_victory_notification(
                match.player_1, match.player_2.username, match_id=match.id,
            )
            Emails.send_match_lost_notification(
                match.player_2, match.player_1.username, match_id=match.id,
            )
        elif match.winner == match.player_2 and match.player_2 is not None:
            Emails.send_match_victory_notification(
                match.player_2, match.player_1.username, match_id=match.id,
            )
            Emails.send_match_lost_notification(
                match.player_1, match.player_2.username, match_id=match.id,
            )

        from core.metrics.models import track
        track(
            None, "match_completed",
            match_id=str(match.id),
            winner_id=str(match.winner_id) if match.winner_id else None,
            player_1_id=str(match.player_1_id),
            player_2_id=str(match.player_2_id) if match.player_2_id else None,
            format=match.format,
        )

    def _resolve_winner(self, match):
        """The no-draw cascade (see ``calculate_winner``). Returns a User —
        ``None`` only for the degenerate case of a never-accepted match
        (no player_2) whose window expired."""
        if match.player_2 is None:
            return None

        # 1. Regular points.
        p1_score, p2_score, _ = score_match(match)
        if p1_score > p2_score:
            return match.player_1
        if p2_score > p1_score:
            return match.player_2

        # 2. Golden pick.
        side = golden_winner_side(match)
        if side == 1:
            return match.player_1
        if side == 2:
            return match.player_2

        # 3. Boldness: sum of decimal odds across winning picks.
        p1_odds, p2_odds = winning_odds_totals(match)
        if p1_odds > p2_odds:
            return match.player_1
        if p2_odds > p1_odds:
            return match.player_2

        # 4. Golden-total prediction (stored on the TieBreaker row at
        # golden-pick time; NULL = that side never picked the golden).
        tb = match.tiebreaker
        if tb is not None:
            p1_guess, p2_guess = tb.owner_total, tb.player_2_total
            if p1_guess is not None and p2_guess is None:
                return match.player_1
            if p2_guess is not None and p1_guess is None:
                return match.player_2
            if p1_guess is not None and p2_guess is not None and p1_guess != p2_guess:
                actual = TieBreaker.objects.calculate_event_total(tb)
                if actual is not None:
                    d1, d2 = abs(p1_guess - actual), abs(p2_guess - actual)
                    if d1 < d2:
                        return match.player_1
                    if d2 < d1:
                        return match.player_2
                    # Equidistant with different guesses → exactly one is
                    # under. Under beats over (price-is-right convention).
                    return match.player_1 if p1_guess < p2_guess else match.player_2
                # Event total unknowable (postponed/canceled golden event):
                # predictions can't be judged — fall through.

        # 5. Dead heat: the accepter wins. Deterministic, known upfront,
        # and the match creator can never farm a tie.
        return match.player_2


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

    # Format preset fixed at creation (D-5 #4) — window length and game
    # count derive from it (core.match.formats). Pre-format matches were
    # all the 5-games/7-day shape, i.e. exactly MARATHON.
    format = models.CharField(
        max_length=10,
        choices=formats.FORMAT_CHOICES,
        default=formats.DEFAULT_FORMAT,
    )

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
    def games_per_player(self):
        return formats.games_per_player(self.format)

    @property
    def format_label(self):
        return formats.format_label(self.format)

    @property
    def window(self):
        return formats.format_window(self.format)

    @property
    def golden_game(self):
        return self.games.filter(is_golden=True).first()

    def regular_games_for(self, user):
        return self.games.filter(owner=user, is_golden=False).order_by("slot")
