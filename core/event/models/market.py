from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from core.event.models.bookmaker import Bookmaker

class MarketManager(AbstractManager):
    pass

class Market(AbstractModel):
    bookmaker = models.ForeignKey(Bookmaker, on_delete=models.CASCADE, related_name='markets')
    key = models.CharField(max_length=255)
    last_update = models.DateTimeField()

    objects = MarketManager()

    class Meta:
        db_table = 'core.market'

    def __str__(self):
        return f"{self.key} - {self.last_update}"
