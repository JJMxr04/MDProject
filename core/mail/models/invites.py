import uuid
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from core.user.models import User
from core.abstract.models import AbstractManager


from .models import Emails
import importlib



INVITE_TYPE_CHOICES = (
    ('tournament', 'Tournament'),
    ('match', 'Match'),
    # Friend-request approval — sender → player handshake. Replaces the
    # old "click Add Friend → instant bilateral add" flow.
    ('friend', 'Friend'),
)

class InviteManager(AbstractManager):
    def create_invite(self, obj_id, player, invite_type, sender, accepted=False, accepted_date=None, invited_date=None):
        invite = self.create(
            obj_id=obj_id,
            player=player,
            type=invite_type,
            sender=sender,
            accepted=accepted,
            accepted_date=accepted_date,
            invited_date=invited_date,
        )
        if invite_type == 'match':
            Emails.send_match_invite(player, sender.username)

        if invite_type == 'tournament':
            from core.tournament.models import Tournament
            tournament = Tournament.objects.get(id=obj_id)
            Emails.send_tournament_invite(player, tournament)

        if invite_type == 'friend':
            # Friend invites — best-effort notification; no failure.
            try:
                Emails.send_friend_invite(player, sender.username)
            except AttributeError:
                # Mail backend hasn't grown ``send_friend_invite`` yet —
                # the invite still records, user sees it in /portal/mail/invites.
                pass

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

    @transaction.atomic
    def accept_invite(self, invite):
        """Accept an invite and trigger the side-effects (Match creation /
        Tournament join). Atomic — if Match creation raises (e.g.
        ``GoldenGameUnavailable`` from the catalog), the invite stays in its
        original state so the user can retry later.

        Lets domain exceptions propagate to the view so it can return a
        user-friendly error message; only suppresses unexpected system
        errors via the outer view's generic except.
        """
        # Re-fetch under a row lock. Without it, two concurrent accepts both
        # pass the view's ownership check and create duplicate side-effects
        # (two Matches from one invite). The loser of the lock race sees the
        # row deleted and raises DoesNotExist → the view's 404.
        invite = self.select_for_update().get(pk=invite.pk)
        if invite.state != 'sent':
            raise self.model.DoesNotExist("Invite already handled.")

        invite.accepted = True
        invite.accepted_date = timezone.now()
        invite.state = "accepted"
        invite.save()

        if invite.type == 'match':
            from core.match.models import Match
            # May raise GoldenGameUnavailable — @transaction.atomic rolls
            # back the invite state above so the user can retry.
            Match.objects.create_match(player_1=invite.sender, player_2=invite.player)
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
            # Bilateral friendship is created at acceptance time, not at
            # invite-creation time. Either side can rescind by deleting the
            # invite before it's accepted; once accepted both User.friends
            # M2M rows are written.
            invite.sender.add_friend(invite.player)
            invite.player.add_friend(invite.sender)
        invite.delete()
        return True

class Invite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    obj_id = models.UUIDField(null=True,blank=True)  # Stores the UUID of the referenced object (e.g., Tournament, Match)
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_invites')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_invites')  # User who sent the invite
    type = models.CharField(max_length=20, choices=INVITE_TYPE_CHOICES)  # 'tournament', 'match', etc.
    accepted = models.BooleanField(default=False)
    accepted_date = models.DateTimeField(null=True)
    invited_date = models.DateTimeField(null=True)
    state = models.CharField(max_length=20, default='sent')  # sent, expired, accepted, declined

    objects = InviteManager()

    class Meta:
        db_table = 'core_invites'

    def __str__(self):
        return f"Invite from {self.sender.username} to {self.player.username} ({self.get_type_display()})"
