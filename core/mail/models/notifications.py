from django.db import models
from core.user.models import User
import uuid


class NotificationManager(models.Manager):
    def get_notifications(self,user):

        return self.filter(user=user).all()

    def mark_read(self, id, user):
        # Ownership-scoped: only the recipient may mark their own notification
        # read. Filtering by (id, user) means another user's id matches no row
        # -> DoesNotExist -> the view returns 404 (existence not leaked).
        # See findings.md S-13 (IDOR).
        notification = self.filter(id=id, user=user).first()
        if notification is None:
            raise self.model.DoesNotExist
        notification.delete()  # Delete the notification

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


    # Use Manager as the default manager
    objects = NotificationManager()

    class Meta:
        db_table = 'core_mail_notification'

    def __str__(self):
        return self.message
