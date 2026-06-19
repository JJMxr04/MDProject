"""Invite-to-non-user (plan Phase 4 §3, D-4b).

A ``PendingInvite`` targets an *email address*, not a User row. The invite
email carries a signed signup URL; when the recipient registers with that
email, every valid pending invite for it is consumed: the friend edge is
written and, for match invites, the real ``Invite`` is materialized with
its payload (format, …) so the new user lands with the challenge waiting.

A valid pending invite also satisfies the waitlist gate at registration —
being asked-for by a friend IS the access grant (RegisterForm.clean_email).

The tokenless variant is each user's referral link (?ref=<friend_code>):
same consumption idea, but it only creates the friend edge and does NOT
bypass the waitlist.
"""

import uuid
from datetime import timedelta

from django.core import signing
from django.db import models, transaction
from django.utils import timezone

from core.user.models import User

PENDING_INVITE_EXPIRY = timedelta(days=14)

_TOKEN_SALT = "core.mail.pending-invite"


class PendingInviteManager(models.Manager):
    def create_pending(self, *, inviter, email, invite_type='friend', payload=None):
        """Create (or return the existing) pending invite for this
        (inviter, email) pair. Idempotent within the expiry window — a
        re-invite returns ``(invite, False)`` and the caller skips the
        email re-send.
        """
        email = User.objects.normalize_email(email).lower()
        existing = self.valid().filter(inviter=inviter, email=email).first()
        if existing is not None:
            return existing, False
        pending = self.create(
            inviter=inviter,
            email=email,
            invite_type=invite_type,
            payload=payload or {},
            expires_at=timezone.now() + PENDING_INVITE_EXPIRY,
        )
        return pending, True

    def valid(self):
        return self.filter(consumed_at__isnull=True, expires_at__gt=timezone.now())

    def valid_for_email(self, email):
        return self.valid().filter(email=(email or "").strip().lower())

    @transaction.atomic
    def consume_for_user(self, user):
        """Consume every valid pending invite addressed to ``user.email``:
        friend edge + materialized Invite (match type), stamped consumed.

        Called once from the registration flow after the User row exists.
        Returns the number of invites consumed. Never raises — signup must
        not break because an inviter deleted their account mid-flight.
        """
        consumed = 0
        pendings = (
            self.valid_for_email(user.email)
            .select_for_update()
            .select_related('inviter')
        )
        for pending in pendings:
            inviter = pending.inviter
            if inviter is None or inviter.pk == user.pk:
                pending.consumed_at = timezone.now()
                pending.save(update_fields=['consumed_at'])
                continue
            # The friend edge always — the invite is a friendship claim
            # regardless of type (D-4b). M2M is symmetric: one add suffices.
            inviter.add_friend(user)
            if pending.invite_type == 'match':
                from core.mail.models.invites import Invite
                Invite.objects.create_invite(
                    obj_id=None,
                    player=user,
                    invite_type='match',
                    sender=inviter,
                    payload=pending.payload or {},
                )
            pending.consumed_at = timezone.now()
            pending.save(update_fields=['consumed_at'])
            consumed += 1
            from core.metrics.models import track
            track(user, "signup_invite_consumed",
                  inviter_id=str(inviter.pk), invite_type=pending.invite_type)
        return consumed

    def resolve_token(self, token, max_age=None):
        """Token → PendingInvite, or None for tampered/unknown/expired/
        consumed tokens. Used to prefill the signup form; consumption is
        keyed by email (``consume_for_user``), not by token."""
        try:
            pk = signing.loads(token, salt=_TOKEN_SALT)
        except signing.BadSignature:
            return None
        return self.valid().filter(pk=pk).first()


class PendingInvite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    inviter = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='pending_invites_sent',
    )
    invite_type = models.CharField(max_length=20, default='friend')
    # Mirrors Invite.payload — for match invites, the format the materialized
    # Invite will carry (Phase 5 §2).
    payload = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PendingInviteManager()

    class Meta:
        db_table = 'core_pending_invites'

    def __str__(self):
        return f"PendingInvite to {self.email} from {self.inviter_id}"

    @property
    def token(self):
        """Signed token for the signup URL (Django signing — tamper-proof,
        no secret stored on the row)."""
        return signing.dumps(str(self.pk), salt=_TOKEN_SALT)

    @property
    def is_valid(self):
        return self.consumed_at is None and self.expires_at > timezone.now()
