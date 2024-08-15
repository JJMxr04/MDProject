from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from .market import Market

class OutcomeManager(AbstractManager):
    pass

class Outcome(AbstractModel):
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='outcomes', db_index=True)
    name = models.CharField(max_length=50)
    price = models.FloatField()
    point = models.FloatField(null=True)

    objects = OutcomeManager()

    class Meta:
        db_table = 'core.outcome'
        indexes = [
            models.Index(fields=['market', 'name']),  # Composite index for market and name
        ]

    def __str__(self):
        return f"{self.name} - {self.price}"

