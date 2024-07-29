from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
import uuid
import os
from django.core.files.uploadedfile import SimpleUploadedFile

def upload_to_path(instance, filename):
    return os.path.join('teamLogos', instance.country, instance.title, instance.team_name, filename)

class TeamManager(AbstractManager):
    def get_object_by_team_name(self, team_name):
        try:
            instance = self.get(team_name=team_name)
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            raise Http404("Team does not exist")

    def get_object_by_team_id(self, team_id):
        try:
            instance = self.filter(team_id=team_id).first()
            return instance
        except (ObjectDoesNotExist, ValueError, TypeError):
            return None

    def create_team(self, team_name, title, group, team_id, logo_content, country, country_code):
        team = self.get_object_by_team_id(team_id)
        if team is None:
            team = self.model(
                team_name=team_name,
                title=title,
                group=group,
                team_id=team_id,
                country=country,
                country_code=country_code
            )
            if logo_content:
                logo_file = SimpleUploadedFile(f"{team_id}.png", logo_content)
                team.logo_url = logo_file
            team.save(using=self._db)
            return team
        else:
            return team

class Team(AbstractModel):
    public_id = models.UUIDField(db_index=True, unique=True, default=uuid.uuid4, editable=False)
    team_name = models.CharField(max_length=255, unique=True, null=False, blank=False)
    title = models.CharField(max_length=255)
    group = models.CharField(max_length=255)
    team_id = models.CharField(max_length=255, default=None, null=True, blank=True)
    logo_url = models.ImageField(upload_to=upload_to_path, null=True, blank=True)
    country = models.CharField(max_length=255, default=None, null=True, blank=True)
    country_code = models.CharField(max_length=10, default=None, null=True, blank=True)

    objects = TeamManager()

    class Meta:
        db_table = "'core.team'"

    def __str__(self):
        return f"{self.team_name}"
