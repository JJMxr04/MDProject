from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404


class EventManager(AbstractManager):
    @classmethod
    def get_sport_state(cls, event_id, completed, event_scores, score1, score2):
        event = cls.get_object_by_public_id(event_id)

        if event is ObjectDoesNotExist:
            return Http404

        if event.completed != completed:
            event.completed = completed
            event.scores = event_scores

            if score1['score'] > score2['score']:
                event.winner = score1['name']
            elif score1['score'] < score2['score']:
                event.winner = score2['name']
            else:
                event.winner = 'Tie'

            event.save()

        return event

    @classmethod
    def get_upcoming_sport_events(cls, sport_key):
        try:
            instance = cls.get(sport_key=sport_key, completed=False)
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return Http404


    def get_active_events(self):
        try:
            instance = self.filter(completed=False)
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return Http404

    @classmethod
    def get_random_golden(cls):
        # Get the current time
        current_time = datetime.utcnow()
        min_commence_time = current_time + timedelta(days=5)
        max_commence_time = current_time + timedelta(days=7)
        try:
            instance = cls.filter(
                commence_time__range=(min_commence_time, max_commence_time)
            ).first()
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return Http404


class Event(AbstractModel):
    sport_key = models.CharField(max_length=255)
    sport_title = models.CharField(max_length=255)
    commence_time = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)
    home_team = models.CharField(max_length=255)
    away_team = models.CharField(max_length=255)
    scores = models.CharField(max_length=255, null=True)
    winner = models.CharField(max_length=255, null=True, default=None)

    objects = EventManager()

    class meta:
        db_table = "'core.event'"
