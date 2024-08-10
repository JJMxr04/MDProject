from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.event.models.team import Team



class EventManager(AbstractManager):
    def get_event_state(self, event_id, completed, event_scores, score1, score2):
        event = self.get_object_by_id(event_id)
        if event is ObjectDoesNotExist:
            return None
        if event.completed == True:
            event.completed = completed
            event.scores = event_scores
            if score1['score'] > score2['score']:
                event.winner = score1['name']
            if score1['score'] < score2['score']:
                event.winner = score2['name']
            if score1['score'] == score2['score']:
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

    def get_random_golden(self):
        # Get the current time
        current_time = datetime.utcnow()
        min_commence_time = current_time + timedelta(days=5)
        max_commence_time = current_time + timedelta(days=7)
        try:
            instance = self.filter(commence_time__range=(min_commence_time, max_commence_time),completed=False).first()
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return Http404

class Event(AbstractModel):
    sport_key = models.CharField(max_length=255)
    sport_title = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    group = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    commence_time = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)
    home_team = models.CharField(max_length=255)
    home_team_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_team_team', null=True, blank=True)
    away_team = models.CharField(max_length=255)
    away_team_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_team_team', null=True, blank=True)
    scores = models.CharField(max_length=255, null=True, default=None)
    winner = models.CharField(max_length=255, null=True, default=None)

    objects = EventManager()

    class Meta:
        db_table = 'core_event_event'

    def __str__(self):
        return f"{self.home_team} Vs {self.away_team}"