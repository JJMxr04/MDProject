import uuid
from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from core.user.models import User
from core.abstract.models import AbstractManager


from .models import Emails



INVITE_TYPE_CHOICES = (
    ('tournament', 'Tournament'),
    ('match', 'Match'),
    # Friend-request approval — sender → player handshake. Replaces the
    # old "click Add Friend → instant bilateral add" flow.
    ('friend', 'Friend'),
)

# Invite lifecycle (plan Phase 4 §2). 'sent' is the only actionable state;
# everything else is terminal and kept for the invite-list history.
INVITE_STATE_CHOICES = (
    ('sent', 'Sent'),
    ('accepted', 'Accepted'),
    ('declined', 'Declined'),
    ('canceled', 'Canceled'),
    ('expired', 'Expired'),
)

# Default expiry window per invite type. Match invites instead default to
# their format's window (a stale Tuesday invite to a weekend Blitz is
# meaningless) — see ``default_expiry``.
INVITE_EXPIRY_DEFAULT = timedelta(days=14)


class InviteExpired(Exception):
    """Raised by ``accept_invite`` when the invite's window has passed.
    Message is user-facing — the view surfaces it in the portal toast."""


class InviteManager(AbstractManager):
    @staticmethod
    def default_expiry(invite_type, payload, invited_date):
        """Expiry stamp for a new invite: format window for match invites,
        a generous fixed window for everything else."""
        if invite_type == 'match':
            from core.match import formats
            fmt = formats.normalize_format((payload or {}).get('format'))
            return invited_date + formats.format_window(fmt)
        return invited_date + INVITE_EXPIRY_DEFAULT

    def create_invite(self, obj_id, player, invite_type, sender,
                      accepted=False, accepted_date=None, invited_date=None,
                      payload=None, expires_at=None):
        invited_date = invited_date or timezone.now()
        payload = payload or {}
        if expires_at is None:
            expires_at = self.default_expiry(invite_type, payload, invited_date)
        invite = self.create(
            obj_id=obj_id,
            player=player,
            type=invite_type,
            sender=sender,
            accepted=accepted,
            accepted_date=accepted_date,
            invited_date=invited_date,
            payload=payload,
            expires_at=expires_at,
        )
        if invite_type == 'match':
            if (payload or {}).get('duel'):
                Emails.send_duel_invite(player, sender.username, payload)
            else:
                Emails.send_match_invite(
                    player, sender.username,
                    format_label=invite.format_label,
                )

        if invite_type == 'tournament':
            from core.tournament.models import Tournament
            tournament = Tournament.objects.get(id=obj_id)
            Emails.send_tournament_invite(player, tournament)

        if invite_type == 'friend':
            Emails.send_friend_invite(player, sender.username)

        from core.metrics.models import track
        track(sender, "invite_sent", invite_type=invite_type, invite_id=str(invite.pk))
        return invite


    def update_invite(self, invite, **kwargs):
        for key, value in kwargs.items():
            setattr(invite, key, value)
        invite.save()
        return invite

    def delete_invite(self, invite):
        invite.delete()

    def check_invite(self, obj_id, user, invite_type):
        try:
            invite = self.get(obj_id=obj_id, player=user, type=invite_type)
            return True
        except ObjectDoesNotExist:
            return False

    def get_invites(self, obj_id, invite_type):
        return self.filter(obj_id=obj_id, type=invite_type)

    def accept_invite(self, invite):
        """Accept an invite and trigger the side-effects (Match creation /
        Tournament join). Atomic — if Match creation raises (e.g.
        ``GoldenGameUnavailable`` from the catalog), the invite stays in its
        original state so the user can retry later.

        Lets domain exceptions propagate to the view so it can return a
        user-friendly error message; only suppresses unexpected system
        errors via the outer view's generic except.
        """
        try:
            return self._accept_invite_locked(invite)
        except InviteExpired:
            # The flip inside the atomic block rolled back with everything
            # else — persist it here, post-rollback, so the row doesn't
            # stay 'sent' until the nightly cron. Guarded on state so a
            # concurrent handler can't be overwritten.
            self.filter(pk=invite.pk, state='sent').update(state='expired')
            raise

    @transaction.atomic
    def _accept_invite_locked(self, invite):
        # Re-fetch under a row lock. Without it, two concurrent accepts both
        # pass the view's ownership check and create duplicate side-effects
        # (two Matches from one invite). The loser of the lock race sees the
        # state already flipped and raises DoesNotExist → the view's 404.
        invite = self.select_for_update().get(pk=invite.pk)
        if invite.state != 'sent':
            raise self.model.DoesNotExist("Invite already handled.")

        # Lazy expiry check (Phase 4 §2) — the nightly cron flips stale rows
        # too, but an accept between cron runs must not slip through. The
        # raise aborts this transaction; accept_invite persists the flip.
        if invite.expires_at and invite.expires_at <= timezone.now():
            raise InviteExpired(
                "This invite has expired — ask your friend to send a new one."
            )

        invite.accepted = True
        invite.accepted_date = timezone.now()
        invite.state = "accepted"
        invite.save()

        if invite.type == 'match':
            from core.match.models import Match
            payload = invite.payload or {}
            if payload.get('duel'):
                # Duel (phase 14): one game, sides set at accept, settles at
                # event end. May raise DuelError if the event vanished from the
                # catalog — @transaction.atomic rolls the invite state back.
                Match.objects.create_duel(invite)
            else:
                # May raise GoldenGameUnavailable / FixtureUnavailable —
                # @transaction.atomic rolls back the invite state above so the
                # user can retry. The format rides on the invite payload
                # (D-5 #4: accept = consent to the displayed format).
                Match.objects.create_match(
                    player_1=invite.sender,
                    player_2=invite.player,
                    match_format=payload.get('format'),
                )
            # Notify both sides — the sender (their invite was accepted)
            # and the accepter (they just joined a match).
            Emails.send_match_acceptance_confirmation(invite.sender, invite.player.username)
            Emails.send_match_started_to_accepter(invite.player, invite.sender.username)
        if invite.type == 'tournament':
            from core.tournament.models import Tournament
            from core.tournament.models.tournament import TournamentJoinUnavailable
            try:
                tournament = Tournament.objects.get(id=invite.obj_id)
            except Tournament.DoesNotExist:
                raise TournamentJoinUnavailable("This tournament no longer exists.")
            # Actually enroll — without this the user gets a "you're in!"
            # email while never appearing in the bracket.
            if not Tournament.objects.accept_invite(tournament.id, invite.player):
                raise TournamentJoinUnavailable(
                    "This tournament is full, already started, or no longer taking players."
                )
            Emails.send_tournament_acceptance_confirmation(invite.player, tournament)
        if invite.type == 'friend':
            # Friendship is created at acceptance time, not at invite-
            # creation time. User.friends is symmetric — one add writes
            # both directions (the single friend-storage truth, D-4a).
            invite.sender.add_friend(invite.player)

        from core.metrics.models import track
        track(invite.player, "invite_accepted", invite_type=invite.type, invite_id=str(invite.pk))
        return True

    @transaction.atomic
    def decline_invite(self, invite):
        """Player declines: terminal state + the sender is notified through
        the ``Emails._notify`` chokepoint (Phase 4 §2 — decline used to be a
        silent row delete)."""
        invite = self.select_for_update().get(pk=invite.pk)
        if invite.state != 'sent':
            raise self.model.DoesNotExist("Invite already handled.")
        invite.state = 'declined'
        invite.save(update_fields=['state'])
        Emails.send_invite_declined(invite.sender, invite.player.username, invite.type)
        from core.metrics.models import track
        track(invite.player, "invite_declined", invite_type=invite.type, invite_id=str(invite.pk))
        return invite

    @transaction.atomic
    def cancel_invite(self, invite):
        """Sender withdraws an outgoing invite (Phase 4 §2). No email — the
        recipient just sees the invite leave their actionable list."""
        invite = self.select_for_update().get(pk=invite.pk)
        if invite.state != 'sent':
            raise self.model.DoesNotExist("Invite already handled.")
        invite.state = 'canceled'
        invite.save(update_fields=['state'])
        from core.metrics.models import track
        track(invite.sender, "invite_canceled", invite_type=invite.type, invite_id=str(invite.pk))
        return invite

    def expire_stale(self):
        """Nightly cron body: flip overdue ``sent`` rows to ``expired``.
        The accept path also checks lazily, so this is bookkeeping for the
        list views, not the correctness gate."""
        return self.filter(
            state='sent', expires_at__lte=timezone.now(),
        ).update(state='expired')

class Invite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    obj_id = models.UUIDField(null=True,blank=True)  # Stores the UUID of the referenced object (e.g., Tournament, Match)
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_invites')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invites')  # User who sent the invite
    type = models.CharField(max_length=20, choices=INVITE_TYPE_CHOICES)  # 'tournament', 'match', etc.
    accepted = models.BooleanField(default=False)
    accepted_date = models.DateTimeField(null=True)
    invited_date = models.DateTimeField(null=True)
    state = models.CharField(max_length=20, default='sent', choices=INVITE_STATE_CHOICES)
    # Type-specific extras — match invites carry {'format': 'BLITZ'|...,
    # 'rematch_of': '<match uuid>'} (Phase 5 §2). Never trusted blindly:
    # readers normalize (e.g. formats.normalize_format).
    payload = models.JSONField(default=dict, blank=True)
    # Past this stamp the invite can't be accepted (lazy check at accept +
    # nightly cron flip). NULL = never expires (legacy rows).
    expires_at = models.DateTimeField(null=True, blank=True)

    objects = InviteManager()

    class Meta:
        db_table = 'core_invites'

    def __str__(self):
        return f"Invite from {self.sender.username} to {self.player.username} ({self.get_type_display()})"

    @property
    def effective_state(self):
        """Display state — shows overdue ``sent`` rows as expired without
        waiting for the nightly cron to flip them."""
        if (
            self.state == 'sent'
            and self.expires_at is not None
            and self.expires_at <= timezone.now()
        ):
            return 'expired'
        return self.state

    @property
    def format_label(self):
        """Human label for a match invite's format payload (None otherwise)."""
        if self.type != 'match':
            return None
        from core.match import formats
        return formats.format_label((self.payload or {}).get('format'))
