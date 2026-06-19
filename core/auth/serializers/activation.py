from django.contrib.auth.models import update_last_login
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings

from core.user.serializers import UserSerializer


class ActivateSerializer(TokenObtainPairSerializer):
    token = serializers.CharField()
