from rest_framework import serializers
from core.mail.models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'user', 'message', 'created_at']


class NotificationV1Serializer(serializers.ModelSerializer):
    """v1 read serializer for the notifications island (plan 03/07).

    Explicit fields, all read-only — mutations happen through dedicated
    mark-read/clear actions (never field writes), and reading or clearing a
    notification deletes it (so there is no read/cleared state to surface). The
    owning ``user`` is NOT exposed (it's implied by the scoped queryset; leaking
    it would serve no purpose and widen the surface).
    """

    class Meta:
        model = Notification
        fields = ['id', 'message', 'created_at']
        read_only_fields = fields