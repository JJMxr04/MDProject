from rest_framework import serializers
from core.user.models import User
from core.match.models import TieBreaker

class TieBreakerSerializer(serializers.ModelSerializer):
    winner = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)

    class Meta:
        model = TieBreaker
        fields = ['id', 'winner']