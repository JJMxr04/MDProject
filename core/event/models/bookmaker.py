from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from .market import Market
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.event.models.team import Team



class BookmakerManager(AbstractManager):
    pass


class Bookmaker(AbstractModel):
    key = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    last_update = models.DateTimeField()
    markets = models.ManyToManyField(Market, related_name="bookmakers")
    objects = BookmakerManager

    class meta:
        db_table = "'core.bookmarker'"

    def __str__(self):
        return f"{self.title}"