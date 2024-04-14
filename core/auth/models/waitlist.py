from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone
import uuid

class WaitlistEntryManager(models.Manager):
    def create_entry(self, email, full_name, description="", registered=False, activated=False, admin_granted_access=False):
        entry = self.model(
            email=email,
            full_name=full_name,
            description=description,
            registered=registered,
            activated=activated,
            admin_granted_access=admin_granted_access
        )
        entry.save(using=self._db)
        return entry

    def approve_waitlist_entry(self, pid):
        entry = self.get(id=pid)
        entry.admin_granted_access = True
        entry.save(using=self._db)
        return entry

    def get_all_wailtlist_entries(self):
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


class WaitlistEntry(models.Model):
    id = models.UUIDField(db_index=True, unique=True, default=uuid.uuid4, editable=False, primary_key=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    email = models.EmailField(unique=True)
    description = models.TextField(blank=True)
    full_name = models.CharField(max_length=100)
    registered = models.BooleanField(default=False)
    registered_at = models.DateTimeField(null=True, blank=True)
    activated = models.BooleanField(default=False)
    admin_granted_access = models.BooleanField(default=False)

    objects = WaitlistEntryManager()

    def __str__(self):
        return self.email
