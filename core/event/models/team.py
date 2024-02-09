from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
import uuid


class TeamManager(AbstractManager):
    def get_object_by_team_name(self, team_name):
        try:
            instance = self.get(team_name=team_name)
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return Http404

    def create_team(self, team_name, title, group,team_id,logo_url,country,country_code,):
        """Create and return a `User` with an email, phone number, username and password."""

        team = self.model(team_name=team_name, title=title,group=group,team_id=team_id,logo_url=logo_url,country=country,country_code=country_code)
        team.save(using=self._db)
        return team


class Team(AbstractModel):
    public_id = models.UUIDField(db_index=True, unique=True, default=uuid.uuid4, editable=False)
    team_name = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    group = models.CharField(max_length=255)
    team_id = models.CharField(max_length=255,default=None, null=True, blank=True)
    logo_url = models.CharField(max_length=255,default=None, null=True, blank=True)
    country =  models.CharField(max_length=255,default=None, null=True, blank=True)
    country_code = models.CharField(max_length=10,default=None, null=True, blank=True)


    objects = TeamManager()

    class meta:
        db_table = "'core.team'"