from django.db import models
from core.abstract.models import AbstractModel, AbstractManager
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404


class SportManager(AbstractManager):

    def get_sport_state(self, key, active, has_outrights):

        sport = self.filter(key=key).first()
        if sport == None:
            return False
        if (sport.active is not active):
            sport.active = active
            sport.has_outrights = has_outrights
            models.session.commit()
        return True  # There is a sport and Modification successful is completed

    def get_active_sports(self):
        active_sports = self.filter(active=True).all()
        keys = []
        if active_sports:
            for active_sport in active_sports:
                keys.append(active_sport.key)
            return keys  # Modification successful
        else:
            return False

    def get_all_sport_keys(self):
        try:
            # Query all distinct keys from the Event table
            keys = self.values('key').distinct()

            # Extract keys from the result and convert them to a list
            key_list = [key[0] for key in keys]

            return key_list
        except Exception as e:
            print(f"An error occurred: {e}")
            return None




class Sport(AbstractModel):
    key = models.CharField(max_length=255, primary_key=True)
    group = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    active = models.BooleanField(default=False)
    has_outrights = models.BooleanField(default=False)

    objects = SportManager()

    class Meta:
        db_table = 'core_sport'
