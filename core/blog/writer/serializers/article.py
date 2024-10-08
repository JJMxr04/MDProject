from rest_framework import serializers
from core.abstract.serializers import AbstractSerializer
from core.blog.writer.models import Article
from core.event.serializers.event import EventSerializer
from core.event.serializers.outcome import  OutcomeSerializer  # Import the necessary serializers



class ArticleSerializer(serializers.Serializer):


    event = EventSerializer()  # Use EventSerializer for events
    outcome = OutcomeSerializer()  # Use OutcomeSerializer for outcomes

    class Meta:
        model = Article
        fields = '__all__'
        # read_only_fields = ['created', 'updated']