from rest_framework import serializers
from core.mail.models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'user', 'message', 'created_at']


class NotificationV1Serializer(serializers.ModelSerializer):
    """v1 read serializer for the notifications island (plan 03/07).

    Explicit fields, all read-only — the only mutation is "mark read" (which
    deletes the row), so a client never writes notification fields. The owning
    ``user`` is NOT exposed (it's implied by the scoped queryset; leaking it
    would serve no purpose and widen the surface).
    """

    class Meta:
        model = Notification
        fields = ['id', 'message', 'created_at']
        read_only_fields = fields