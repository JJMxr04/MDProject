from django.db import models
from django.utils import timezone
from core.user.models import User
import uuid


class NotificationManager(models.Manager):
    def get_notifications(self, user):
        return self.filter(user=user).all()

    def unread(self, user):
        """The user's still-actionable notifications — neither read nor
        cleared. This is the badge set."""
        return self.filter(user=user, read_at__isnull=True, cleared_at__isnull=True)

    def mark_read(self, id, user):
        """Mark the user's notification read, or delete it if it was already
        handled (read or cleared). Returns True if the row was deleted.

        Ownership-scoped: filtering by (id, user) means another user's id
        matches no row -> DoesNotExist -> the view returns 404 (existence not
        leaked). See findings.md S-13 (IDOR).
        """
        notification = self.filter(id=id, user=user).first()
        if notification is None:
            raise self.model.DoesNotExist
        return notification.mark_read()

    def clear(self, id, user):
        """Clear the user's notification, or delete it if it was already
        handled (read or cleared). Returns True if the row was deleted.
        Ownership-scoped exactly like ``mark_read``."""
        notification = self.filter(id=id, user=user).first()
        if notification is None:
            raise self.model.DoesNotExist
        return notification.clear()

    def mark_all_read(self, user):
        """Apply the per-item rule across every notification the user owns:
        already-handled rows are deleted, fresh rows are marked read.
        Returns ``{"marked": n, "deleted": m}``."""
        return self._sweep(user, field="read_at")

    def clear_all(self, user):
        """Like ``mark_all_read`` but stamps ``cleared_at`` on fresh rows.
        Returns ``{"cleared": n, "deleted": m}``."""
        result = self._sweep(user, field="cleared_at")
        return {"cleared": result["marked"], "deleted": result["deleted"]}

    def _sweep(self, user, *, field):
        # Already-handled (read or cleared) rows are removed; the rest get the
        # requested timestamp. Two queries, no per-row Python loop.
        handled = self.filter(user=user).exclude(
            read_at__isnull=True, cleared_at__isnull=True
        )
        deleted = handled.count()
        handled.delete()
        marked = self.filter(
            user=user, read_at__isnull=True, cleared_at__isnull=True
        ).update(**{field: timezone.now()})
        return {"marked": marked, "deleted": deleted}

    def create_notification(self, user, message):
        # Ensure the user and message are valid
        if not isinstance(user, User):
            raise ValueError("Invalid user instance")
        if not message:
            raise ValueError("Message cannot be empty")

        # Create and return a Notification instance
        notification = self.create(user=user, message=message)
        return notification


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    # Lifecycle: a notification starts fresh (both null), is read OR cleared
    # once (one timestamp set), then a second mark/clear action deletes it.
    read_at = models.DateTimeField(null=True, blank=True)
    cleared_at = models.DateTimeField(null=True, blank=True)

    # Use Manager as the default manager
    objects = NotificationManager()

    class Meta:
        db_table = 'core_mail_notification'

    def __str__(self):
        return self.message

    @property
    def is_handled(self) -> bool:
        """Has this notification already been read or cleared?"""
        return self.read_at is not None or self.cleared_at is not None

    def mark_read(self) -> bool:
        """Stamp ``read_at``, or delete the row if it was already handled.
        Returns True if the row was deleted."""
        if self.is_handled:
            self.delete()
            return True
        self.read_at = timezone.now()
        self.save(update_fields=["read_at"])
        return False

    def clear(self) -> bool:
        """Stamp ``cleared_at``, or delete the row if it was already handled.
        Returns True if the row was deleted."""
        if self.is_handled:
            self.delete()
            return True
        self.cleared_at = timezone.now()
        self.save(update_fields=["cleared_at"])
        return False
