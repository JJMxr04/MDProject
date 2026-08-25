import hashlib

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from core.abstract.image_security import process_image, validate_image_file
from core.abstract.serializers import AbstractSerializer
from core.user.models import User


class AvatarBytesField(serializers.Field):
    """Write: validate + re-encode upload to WEBP, stash bytes for the
    serializer to persist into UserAvatar (BYTEA). Read: emit the user's
    ``avatar_url`` serve string (or None).

    Field name stays ``avatar`` for API stability, but it no longer maps to
    the S3 ImageField — neither read nor write touches storage.
    """

    def get_attribute(self, instance):
        return instance  # pass the User through to to_representation

    def to_representation(self, user):
        return user.avatar_url

    def to_internal_value(self, data):
        validate_image_file(data)          # raises ValidationError on bad input
        return process_image(data).read()  # WEBP bytes


def persist_user_avatar(user, avatar_bytes):
    """Store re-encoded WEBP bytes into the user's UserAvatar row."""
    from core.user.models import UserAvatar

    etag = hashlib.sha256(avatar_bytes).hexdigest()[:32]
    UserAvatar.objects.update_or_create(
        user=user,
        defaults={
            "image": avatar_bytes, "content_type": "image/webp",
            "byte_size": len(avatar_bytes), "etag": etag,
            "status": "ok", "source": "upload",
        },
    )


class UserSerializer(AbstractSerializer):
    # Rewriting some fields like the public id to be represented as the id of the object
    id = serializers.UUIDField(source='public_id', read_only=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)
    # Avatar is validated and re-encoded to WEBP on write, then persisted into
    # the UserAvatar BYTEA store (not S3). Read emits avatar_url. The field
    # name stays ``avatar`` for API stability. See AvatarBytesField.
    avatar = AvatarBytesField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'bio', 'avatar', 'email', 'is_active',
                  'created', 'updated', 'is_admin', 'is_staff', 'activated_link']
        # NOTE: `read_only_fields` (plural). The previous `read_only_field`
        # (singular) was silently ignored by DRF, leaving is_staff/is_admin/
        # is_active WRITABLE — a privilege-escalation primer.
        # Privilege + identity fields are now genuinely read-only.
        read_only_fields = ['id', 'is_active', 'is_admin', 'is_staff', 'activated_link',
                            'created', 'updated']

    def create(self, validated_data):
        # avatar is no longer a model field — pop before the model super() call.
        avatar_bytes = validated_data.pop('avatar', None)
        portal_password = validated_data.pop('portal_password', None)
        user = super().create(validated_data)
        if portal_password:
            user.set_portal_password(portal_password)
        if avatar_bytes:
            persist_user_avatar(user, avatar_bytes)
        return user

    def update(self, instance, validated_data):
        # avatar is no longer a model field — pop before the model super() call.
        avatar_bytes = validated_data.pop('avatar', None)
        portal_password = validated_data.pop('portal_password', None)
        if portal_password:
            instance.set_portal_password(portal_password)
        user = super().update(instance, validated_data)
        if avatar_bytes:
            persist_user_avatar(user, avatar_bytes)
        return user

class PublicUserSerializer(AbstractSerializer):
    # Rewriting some fields like the public id to be represented as the id of the object
    id = serializers.UUIDField(source='public_id', read_only=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, user):
        return user.avatar_url

    class Meta:
        model = User
        # List of all the fields that can be included in a request or a response
        fields = ['id', 'username', 'avatar']
        # List of all the fields that can only be read by the user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        from core.user.models import User
        token = super().get_token(user)

        token["user_id"] = user.id
        token["email"] = user.email
        token["role"] = "admin" if user.is_staff else "user"

        return token

class UserMeSerializer(AbstractSerializer):
    id = serializers.UUIDField(source='public_id', read_only=True, format='hex')
    created = serializers.DateTimeField(read_only=True)
    updated = serializers.DateTimeField(read_only=True)
    # Reads emit avatar_url; writes persist into the UserAvatar BYTEA store.
    # (UserMeViewSet writes via UserSerializer; this serializer is used for
    # reads.) Field name stays ``avatar``. See AvatarBytesField.
    avatar = AvatarBytesField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'bio', 'avatar', 'email',
                  'created', 'updated']
        # `read_only_fields` (plural) — see UserSerializer note above.
        # Privilege fields aren't in this serializer's `fields`; keep the
        # identity fields read-only with the correct attribute name.
        read_only_fields = ['id', 'created', 'updated']


