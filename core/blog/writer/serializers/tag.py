from rest_framework import serializers
from core.abstract.serializers import AbstractSerializer
from core.blog.writer.models import Tag
 # Import the necessary serializers



class TagSerializer(serializers.Serializer):


    class Meta:
        model = Tag
        fields = '__all__'
