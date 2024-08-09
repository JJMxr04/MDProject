from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from .event import Event

class BookmakerManager(AbstractManager):
    pass

class Bookmaker(AbstractModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='bookmakers')
    key = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    last_update = models.DateTimeField()

    objects = BookmakerManager()

    class Meta:
        db_table = "'core.bookmaker'"

    def __str__(self):
        return f"{self.title}"
