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
        fields = ['id', 'username', 'first_name', 'last_name', 'bio', 'avatar', 'email', 'is_active',
                  'created', 'updated', 'is_admin', 'is_staff', 'activated_link']
        # NOTE: `read_only_fields` (plural). The previous `read_only_field`
        # (singular) was silently ignored by DRF, leaving is_staff/is_admin/
        # is_active WRITABLE — a privilege-escalation primer. See findings.md
        # S-14. Privilege + identity fields are now genuinely read-only.
        read_only_fields = ['id', 'is_active', 'is_admin', 'is_staff', 'activated_link',
                            'created', 'updated']
        # Avatar is exposed read-only — uploads are disabled until S3 is wired.
        extra_kwargs = {'avatar': {'read_only': True}}

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

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'bio', 'avatar', 'email',
                  'created', 'updated']
        # `read_only_fields` (plural) — see UserSerializer note / findings.md
        # S-14. Privilege fields aren't in this serializer's `fields`; keep the
        # identity fields read-only with the correct attribute name.
        read_only_fields = ['id', 'created', 'updated']
        # Avatar is exposed read-only — uploads are disabled until S3 is wired.
        extra_kwargs = {'avatar': {'read_only': True}}


