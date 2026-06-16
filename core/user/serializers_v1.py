"""v1 serializers for the user/friends surface.

Explicit fields only, no privilege/identity leakage. ``FriendSerializer`` is a
read view of a friend row; ``AddFriendSerializer`` validates an inbound friend
code without exposing any user fields back on write.
"""

from rest_framework import serializers

from core.user.models import User


class FriendSerializer(serializers.ModelSerializer):
    """Read-only view of one of the requester's friends."""

    id = serializers.UUIDField(source="public_id", read_only=True, format="hex")
    # avatar reads the UserAvatar BYTEA serve URL, not the S3 ImageField. A
    # SerializerMethodField can't appear in read_only_fields (DRF raises), so
    # read_only_fields below lists only the model-backed fields.
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, user):
        return user.avatar_url

    class Meta:
        model = User
        fields = ["id", "username", "avatar", "friend_code"]
        read_only_fields = ["id", "username", "friend_code"]


class AddFriendSerializer(serializers.Serializer):
    """Add a friend by their friend code. Resolves to a ``User`` in
    ``validate_friend_code`` so the view never trusts a raw id from the body."""

    friend_code = serializers.CharField(max_length=8, write_only=True)

    def validate_friend_code(self, value):
        target = User.objects.filter(friend_code=value).first()
        if target is None:
            raise serializers.ValidationError("No user found with that friend code.")
        request = self.context.get("request")
        if request is not None and target == request.user:
            raise serializers.ValidationError("You can't add yourself.")
        self.context["target"] = target
        return value
