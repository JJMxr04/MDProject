from rest_framework import serializers
from core.abstract.serializers import AbstractSerializer
from core.blog.writer.models import Tag
 # Import the necessary serializers



class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag  # Assuming Tag is your model
        fields = ['id', 'name']  # Ensure these fields are correct
