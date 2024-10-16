import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from core.user.models import User
from core.abstract.models import AbstractManager
from notifications import Notification
from models import Emails
from core.tournament.models import Tournament 

INVITE_TYPE_CHOICES = (
    ('tournament', 'Tournament'),
    ('match', 'Match'),
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
        if invite_type =='match':
            Emails.send_match_invite(player,sender.username)

        if invite_type == 'tournament':
            tournament= Tournament.objects.get(id=obj_id)
            Emails.send_tournament_invite(player,tournament)
        
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
        try:
            invite.accepted = True
            invite.accepted_date = timezone.now()
            invite.state = "accepted"
            invite.save()
            return True
        except ObjectDoesNotExist:
            return False

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
