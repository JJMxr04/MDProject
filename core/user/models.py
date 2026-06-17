import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.http import Http404
from core.abstract.models import AbstractModel, AbstractManager
from django.utils.functional import cached_property
import os
from django.contrib.auth.hashers import make_password, check_password
import random
import string


def user_avatar_upload_path(instance, filename):
    # Retained only because migration 0001_initial imports this symbol by reference
    # (not as a string); the User.avatar ImageField it served has been retired.
    return f"avatars/{instance.public_id.hex}/{uuid.uuid4().hex}.webp"


class UserManager(BaseUserManager, AbstractManager):
    def get_object_by_public_id(self, public_id):
        try:
            instance = self.get(public_id=public_id)
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return Http404

    def get_object_by_email(self, email):
        try:
            instance = self.get(email=email)
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return Http404

    def create_user(self, username, email, password=None, portal_password=None, **kwargs):
        if username is None:
            raise TypeError('Users must have a username.')
        if email is None:
            raise TypeError('Users must have an email.')

        user = self.model(username=username, email=self.normalize_email(email), **kwargs)
        user.set_password(password)
        user.save(using=self._db)

        # Assign user to "Portal Group"
        portal_group, created = Group.objects.get_or_create(name='Portal Group')
        user.groups.add(portal_group)

        return user

    def create_user_ex(self, username, first, last, email, password=None, **kwargs):
        if username is None:
            raise TypeError('Users must have a username.')
        if email is None:
            raise TypeError('Users must have an email.')
        if password is None:
            raise TypeError('User must have a password.')

        user = self.model(username=username, first_name=first, last_name=last, email=self.normalize_email(email),
                          **kwargs)
        user.set_password(password)
        user.save(using=self._db)

        # Assign user to "Portal Group"
        portal_group, created = Group.objects.get_or_create(name='Portal Group')
        user.groups.add(portal_group)

        return user

    def create_superuser(self, username, email, password, **kwargs):
        if password is None:
            raise TypeError('Superusers must have a password.')
        if email is None:
            raise TypeError('Superusers must have an email.')
        if username is None:
            raise TypeError('Superusers must have a username.')

        user = self.create_user(username, email, password, **kwargs)
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)

        return user

    def make_user_staff(self, user):
        user.is_staff = True
        user.save()

    def make_user_admin(self, user):
        user.is_staff = True
        user.is_admin = True
        user.save()

    def get_by_friend_code(self, friend_code):
        try:
            instance = self.get(friend_code=friend_code)
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return Http404


class User(AbstractBaseUser, AbstractModel, PermissionsMixin):
    public_id = models.UUIDField(db_index=True, unique=True, default=uuid.uuid4, editable=False)
    username = models.CharField(db_index=True, max_length=255, unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(db_index=True, unique=True)
    # Date of birth — collected at registration to enforce the 18+ age
    # requirement (Paradise Sports is 18+ only). Nullable so existing rows
    # and admin/superuser creation that predate the field stay valid.
    date_of_birth = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_writer= models.BooleanField(default=False)
    activated_link = models.BooleanField(default=False)
    bio = models.TextField(null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    friends = models.ManyToManyField(
        'self',
        symmetrical=True,
        blank=True,
    )
    friend_code = models.CharField(max_length=8, unique=True, blank=True, null=True)

    # --- Pick of the Day streaks (plan Phase 6). Streak = consecutive
    # product days (NY calendar) with a pick — advanced/reset inside
    # DailyPickManager.record_pick, never recomputed from history.
    potd_current_streak = models.PositiveIntegerField(default=0)
    potd_best_streak = models.PositiveIntegerField(default=0)
    potd_last_pick_date = models.DateField(null=True, blank=True)

    # Master switch for engagement emails (match/tournament/friend
    # notifications). Gated centrally in core.mail.models.Emails._notify —
    # in-app Notification rows still write when this is off. Transactional
    # mail (activation, password reset) ignores it. Toggled by the signed
    # unsubscribe link in every engagement email (core.mail.unsubscribe).
    email_notifications = models.BooleanField(default=True)

    # --- Billing / Aggrigator integration (see subscription-plan/02-data-model.md §"core_user.User additions"). ---
    # Stripe Customer object id (``cus_...``). Captured from the
    # checkout.session.completed webhook on first paid checkout; empty
    # for users who never upgraded.
    stripe_customer_id = models.CharField(max_length=64, blank=True, default='')
    # The aggrigator's TenantUser.id mirror — populated by the signup
    # signal's POST to /v1/internal/users. UUID so it joins cleanly with
    # the aggrigator's ``tenant_user.external_user_id`` column (which is
    # this User's ``public_id``).
    aggrigator_external_id = models.UUIDField(null=True, blank=True, unique=True)
    # LEGACY since the service-key cutover (plan §6.4, roadmap Phase 2):
    # outbound auth now rides the single AGGRIGATOR_SERVICE_KEY setting and
    # nothing in the request path reads or writes this field anymore. Kept
    # (a) to avoid a migration on a hot table, (b) as the storage slot for
    # the staff-only admin rotate action, the one remaining per-user-key
    # escape hatch. Safe to drop in a later cleanup migration.
    aggrigator_api_key = models.CharField(max_length=80, blank=True, default='')

    # --- Matchup avatar tints (matchup-colors-mobile design §7). Users pick
    # their own home + away colors; their avatar in a match-detail hero uses
    # the color for the side they're on. NULL → template/CSS fall back to the
    # standard brand-blue (home) / state-danger (away). max_length=9 mirrors
    # Team's color columns (#RRGGBB or #RRGGBBAA).
    home_color = models.CharField(max_length=9, null=True, blank=True)
    away_color = models.CharField(max_length=9, null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = UserManager()

    def __str__(self):
        return f"{self.email}"

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    @cached_property
    def has_pending_invites(self):
        """True only when there's a received invite still awaiting action —
        i.e. ``effective_state == 'sent'`` (state='sent' and not past expiry).
        Drives the nav invite dot/badge so it isn't lit by old accepted/
        declined/expired invites. cached_property → one query per request even
        though the topbar, bottom bar, and mobile menu all read it."""
        from django.db.models import Q
        from django.utils import timezone
        return self.received_invites.filter(state='sent').filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).exists()

    def add_friend(self, user):
        """Add a new friend"""
        if user != self:
            self.friends.add(user)
            
    def remove_friend(self, user):
        """Remove a friend"""
        self.friends.remove(user)
    
    def get_friends(self):
        """Return QuerySet of all friends"""
        return self.friends.all()
    
    def is_friend(self, user):
        """Check if given user is a friend"""
        return self.friends.filter(id=user.id).exists()

    def save(self, *args, **kwargs):
        if not self.friend_code:
            self.friend_code = self.generate_friend_code()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_friend_code():
        """Generate a random 8-character friend code"""
        while True:
            # Generate code: 8 characters, uppercase letters and numbers
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            # Check if code already exists
            if not User.objects.filter(friend_code=code).exists():
                return code
    
    @classmethod
    def find_by_friend_code(cls, code):
        """Find a user by their friend code"""
        try:
            return cls.objects.get(friend_code=code)
        except cls.DoesNotExist:
            return None

    def regenerate_friend_code(self):
        """Generate a new friend code and save it"""
        self.friend_code = self.generate_friend_code()
        self.save(update_fields=['friend_code'])
        return self.friend_code

    @property
    def avatar_url(self):
        """Serve-endpoint URL for this user's avatar, or None when absent.

        Returns a string (not a FieldFile) so templates' ``{{ user.avatar_url }}``
        and ``{% if user.avatar_url %}`` work after the S3 ImageField is retired.
        Keyed by the opaque ``public_id`` (never the enumerable integer pk).
        Mirrors core.event.models.Team.logo_url.
        """
        try:
            row = self.avatar_row
        except UserAvatar.DoesNotExist:
            return None
        if row.status != "ok":
            return None
        from django.urls import reverse

        return reverse("user-avatar", kwargs={"public_id": self.public_id.hex})


class UserAvatar(models.Model):
    """User avatar bytes stored in MDProject's own Postgres (BYTEA).

    1:1 with User — bytes live in a side table (not on User) so hot User
    queries stay lean, mirroring core.event.models.TeamLogo. ``status`` is
    ``ok`` (bytes present) or ``missing``. ``source`` is ``upload``.
    """

    user = models.OneToOneField(
        "core_user.User",
        on_delete=models.CASCADE,
        related_name="avatar_row",
        primary_key=True,
    )
    image = models.BinaryField(null=True, blank=True, editable=False)
    content_type = models.CharField(max_length=64, null=True, blank=True)
    byte_size = models.PositiveIntegerField(default=0)
    etag = models.CharField(max_length=64, null=True, blank=True)
    # "ok" | "missing"
    status = models.CharField(max_length=16)
    source = models.CharField(max_length=32, default="upload")
    fetched = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_user_avatar"

    def __str__(self):
        return f"{self.user_id} [{self.status}]"



