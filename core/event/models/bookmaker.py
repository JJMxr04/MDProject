from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from .event import Event

class BookmakerManager(AbstractManager):
    pass

class Bookmaker(AbstractModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='bookmakers', db_index=True)
    key = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    last_update = models.DateTimeField(db_index=True)

    objects = BookmakerManager()

    class Meta:
        db_table = 'core.bookmaker'
        indexes = [
            models.Index(fields=['event', 'last_update']),  # Composite index for event and last_update
        ]

    def __str__(self):
        return f"{self.title} - {self.event}"

