from django.db import models
from core.user.models import User


class NotificationManager(models.Manager):
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    # Use MatchManager as the default manager
    objects = NotificationManager()

    class Meta:
        db_table = 'core_mail_notification'

    def __str__(self):
        return self.message
