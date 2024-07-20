# myapp/models.py

from django.db import models
from core.user.models import User

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        db_table = 'core.mail.notification'

    def __str__(self):
        return self.message
