import uuid

from django.db import models

from core.user.models import User


class NotificationManager(models.Manager):
    def get_notifications(self, user):
        return self.filter(user=user).all()

    def unread(self, user):
        """The user's notifications. Reading or clearing a notification deletes
        it, so every row that still exists is unread — this is the badge set."""
        return self.filter(user=user)

    def mark_read(self, id, user):
        """Delete the user's notification — reading dismisses it.

        Ownership-scoped: filtering by (id, user) means another user's id
        matches no row -> DoesNotExist -> the view returns 404 (existence not
        leaked) — closes an IDOR.
        """
        notification = self.filter(id=id, user=user).first()
        if notification is None:
            raise self.model.DoesNotExist
        notification.delete()

    def clear(self, id, user):
        """Delete the user's notification — clearing dismisses it.
        Ownership-scoped exactly like ``mark_read``."""
        notification = self.filter(id=id, user=user).first()
        if notification is None:
            raise self.model.DoesNotExist
        notification.delete()

    def mark_all_read(self, user):
        """Delete every notification the user owns. Returns
        ``{"deleted": n}``."""
        deleted, _ = self.filter(user=user).delete()
        return {"deleted": deleted}

    def clear_all(self, user):
        """Delete every notification the user owns. Returns
        ``{"deleted": n}``."""
        return self.mark_all_read(user)

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

    # Lifecycle: a notification is fresh until it is read or cleared, at which
    # point it is deleted outright (no read/cleared state is retained).

    # Use Manager as the default manager
    objects = NotificationManager()

    class Meta:
        db_table = 'core_mail_notification'

    def __str__(self):
        return self.message

    def mark_read(self) -> None:
        """Reading dismisses the notification — delete it."""
        self.delete()

    def clear(self) -> None:
        """Clearing dismisses the notification — delete it."""
        self.delete()
