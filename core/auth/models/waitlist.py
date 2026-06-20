import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone

from core.mail.models import Emails


class WaitlistEntryManager(models.Manager):
    def create_entry(self, email, full_name, description="", phone_number="", registered=False, activated=False, admin_granted_access=False):
        entry = self.model(
            email=email,
            full_name=full_name,
            description=description,
            phone_number=phone_number,
            registered=registered,
            activated=activated,
            admin_granted_access=admin_granted_access
        )
        entry.save(using=self._db)
        Emails.send_waitlist_thank_you(email=email)
        return entry

    def approve_waitlist_entry(self, pid):
        entry = self.get(id=pid)
        entry.admin_granted_access = True
        return entry

    def get_all_waitlist_entries(self):
        return self.filter(admin_granted_access=False)

    def get_object_by_id(self, pid):
        try:
            instance = self.get(id=pid)
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return None

    def get_object_by_email(self, email):
        try:
            instance = self.get(email=email)
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return None

    def revoke_waitlist_entry(self, pid):
        try:
            entry = self.get(id=pid)
            if entry.admin_granted_access:
                entry.admin_granted_access = False
                entry.save(using=self._db)
                return entry
            else:
                return None  # Entry was not previously granted access
        except ObjectDoesNotExist:
            return None


class WaitlistEntry(models.Model):
    id = models.UUIDField(db_index=True, unique=True, default=uuid.uuid4, editable=False, primary_key=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    email = models.EmailField(unique=True)
    description = models.TextField(blank=True)
    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20, blank=True)  # New field
    registered = models.BooleanField(default=False)
    registered_at = models.DateTimeField(null=True, blank=True)
    activated = models.BooleanField(default=False)
    admin_granted_access = models.BooleanField(default=False)

    objects = WaitlistEntryManager()

    def __str__(self):
        return self.email
