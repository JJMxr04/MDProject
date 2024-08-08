from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from .outcome import Outcome
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.event.models.team import Team



class MarketManager(AbstractManager):
    pass


class Market(AbstractModel):
    key = models.CharField(max_length=255)
    last_update = models.DateTimeField()
    outcomes = models.ManyToManyField(Outcome, related_name="markets")
    objects = MarketManager

    class meta:
        db_table = "'core.market'"


    def __str__(self):
        return f"{self.key} - {self.last_update}"