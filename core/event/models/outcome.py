from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.event.models.team import Team



class OutcomeManager(AbstractManager):
    pass


class Outcome(AbstractModel):
    name = models.CharField(max_length=20)
    price = models.IntegerField()
    point = models.IntegerField()
    objects = OutcomeManager

    class meta:
        db_table = "'core.outcome'"


    def __str__(self):
        return f"{self.name} - {self.price}"