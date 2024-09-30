from django.db import models
from core.user.models import User
from core.event.models import Event, Outcome
from django.utils import timezone
import uuid


class Tag(models.Model):
    
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Article(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    # slug = models.SlugField(max_length=200, unique=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    outcome = models.ForeignKey(Outcome, on_delete=models.CASCADE, blank=True,null=True)
    content = models.TextField(max_length=2000,)
    date_created = models.DateTimeField(auto_now_add=True)
    date_updated = models.DateTimeField(auto_now=True)
    date_published = models.DateTimeField(blank=True, null=True)  # Allow null initially
    tags = models.ManyToManyField(Tag, related_name='articles',blank=True)
    is_published = models.BooleanField(default=False)
    image = models.ImageField(upload_to='articles/', blank=True, null=True)
    # highlight_link = models.CharField(max_length=500,,blank=True)
    is_premium= models.BooleanField(default=False, verbose_name="Premium Article?")

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-date_published']

    def save(self, *args, **kwargs):
        if self.is_published:
            if not self.date_published:
                self.date_published = timezone.now()  # Set date_published when published
        else:
            self.date_published = None  # Remove date_published when unpublished
        super().save(*args, **kwargs)  # Call the original save method