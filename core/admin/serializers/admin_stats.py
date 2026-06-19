# serializers.py
from rest_framework import serializers


class AdminStatsSerializer(serializers.Serializer):
    user_reg_stats = serializers.ListField(child=serializers.DictField())
    waitlist_stats = serializers.ListField(child=serializers.DictField())
    total_users = serializers.IntegerField()
    total_waitlist_users = serializers.IntegerField()

