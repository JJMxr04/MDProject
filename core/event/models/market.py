from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from .bookmaker import Bookmaker

class MarketManager(AbstractManager):
    pass

class Market(AbstractModel):
    bookmaker = models.ForeignKey(Bookmaker, on_delete=models.CASCADE, related_name='markets', db_index=True)
    key = models.CharField(max_length=255)
    last_update = models.DateTimeField(db_index=True)

    objects = MarketManager()

    class Meta:
        db_table = 'core.market'
        indexes = [
            models.Index(fields=['bookmaker', 'last_update']),  # Composite index for bookmaker and last_update
        ]

    def __str__(self):
        return f"{self.key} - {self.last_update}"

