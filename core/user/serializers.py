from rest_framework import serializers

from core.user.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from core.abstract.serializers import AbstractSerializer


class UserSerializer(AbstractSerializer):
    # Rewriting some fields like the public id to be represented as the id of the object
    id = serializers.UUIDField(source='public_id', read_only=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        # List of all the fields that can be included in a request or a response
        fields = ['id', 'username', 'first_name', 'last_name', 'bio', 'avatar', 'email', 'is_active',
                  'created', 'updated','is_admin']
        # List of all the fields that can only be read by the user
        read_only_field = ['is_active','is_admin','id']

class PublicUserSerializer(AbstractSerializer):
    # Rewriting some fields like the public id to be represented as the id of the object
    id = serializers.UUIDField(source='public_id', read_only=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        # List of all the fields that can be included in a request or a response
        fields = ['id', 'username', 'avatar']
        # List of all the fields that can only be read by the user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        from core.user.models import User  # Import User model here
        token = super().get_token(user)

        # Customize the token payload here
        token["user_id"] = user.id
        token["email"] = user.email
        token["role"] = "admin" if user.is_staff else "user"

        return token
