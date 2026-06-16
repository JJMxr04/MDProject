from rest_framework import serializers
from core.user.serializers import UserSerializer
from core.user.models import User


class RegisterSerializer(UserSerializer):
    portal_password = serializers.CharField(max_length=128, min_length=8, write_only=True, required=True)
    # Remove the avatar field inherited from UserSerializer: avatars are not
    # settable at registration (closes an unvalidated anonymous-write path).
    # They are set later via the authenticated update path through
    # SecureImageField. Setting a declared field to None is DRF's documented way
    # to drop an inherited field.
    avatar = None

    class Meta:
        model = User
        fields = ['id', 'bio', 'email', 'username', 'first_name', 'last_name', 'portal_password']

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        user.save()
        return user
