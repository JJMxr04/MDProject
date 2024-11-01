from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.event.models import Event
from django.conf import settings
User = settings.AUTH_USER_MODEL

class Forum(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

class Thread(models.Model):
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="threads")
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title

class Post(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="posts", blank=True, null=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="posts_event", blank=True, null=True)
    content = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Post by {self.created_by} in {self.thread or 'Event'}"

    def clean(self):
        if not self.thread and not self.event:
            raise ValidationError("Post must be associated with either a thread or an event.")
        if self.thread and self.event:
            raise ValidationError("Post cannot be associated with both a thread and an event.")
