from rest_framework import serializers

from core.user.models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from core.abstract.serializers import AbstractSerializer
from core.blog.writer.serializers.tag import TagSerializer


class UserSerializer(AbstractSerializer):
    # Rewriting some fields like the public id to be represented as the id of the object
    id = serializers.UUIDField(source='public_id', read_only=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)

    class Meta:
        model = User
        # List of all the fields that can be included in a request or a response
        fields = ['id', 'username', 'first_name', 'last_name', 'bio', 'avatar', 'email', 'is_active',
                  'created', 'updated', 'is_admin', 'is_staff', 'activated_link']

        # List of all the fields that can only be read by the user
        read_only_field = ['is_active', 'is_admin', 'id', 'is_staff','activated_link']

    def create(self, validated_data):
        portal_password = validated_data.pop('portal_password', None)
        user = super().create(validated_data)
        if portal_password:
            user.set_portal_password(portal_password)
        return user

    def update(self, instance, validated_data):
        portal_password = validated_data.pop('portal_password', None)
        if portal_password:
            instance.set_portal_password(portal_password)
        return super().update(instance, validated_data)

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

class UserMeSerializer(AbstractSerializer):
    id = serializers.UUIDField(source='public_id', read_only=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)

    def update(self, instance, validated_data):
        avatar = validated_data.pop('avatar', None)
        if avatar:
            instance.avatar.save(avatar.name, avatar, save=True)
        return super().update(instance, validated_data)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'bio', 'avatar', 'email',
                  'created', 'updated']
        read_only_field = ['id','created', 'updated','is_active', 'is_admin', 'id', 'is_staff', 'activated_link']

class WriterSerializer(AbstractSerializer):
    # Rewriting some fields like the public id to be represented as the id of the object
    id = serializers.UUIDField(source='public_id', read_only=True, format='hex')
    tags = TagSerializer(many=True)

    class Meta:
        model = User
        # List of all the fields that can be included in a request or a response
        fields = ['id', 'username', 'avatar','first_name','last_name','writer_description','tags']
        # List of all the fields that can only be read by the user

