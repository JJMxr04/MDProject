from rest_framework import serializers
from core.blog.writer.models import SubscriptionPlan

class SubscriptionPlanSerializer(serializers.ModelSerializer):  # Changed to ModelSerializer
    class Meta:
        model = SubscriptionPlan
        fields = ['price']  # Ensure 'price' is included
        # read_only_fields = ['created', 'updated']  # Uncomment if needed