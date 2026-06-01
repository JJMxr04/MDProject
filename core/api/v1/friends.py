"""``/api/v1/friends/`` — the requester's friend list (S-23).

The collection is the requester's own ``friends`` M2M, so it can never surface
another user's edges. ``destroy`` resolves the friend from that scoped queryset
first (a non-friend public_id 404s before anything mutates), then removes the
edge — the explicit ownership assert S-23 asked for. ``create`` adds a friend by
friend code (kept symmetric with the existing M2M semantics).
"""

from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from core.api.base import V1ViewMixin
from core.user.serializers_v1 import AddFriendSerializer, FriendSerializer


class FriendViewSet(
    V1ViewMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"

    def get_serializer_class(self):
        if self.action == "create":
            return AddFriendSerializer
        return FriendSerializer

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            from core.user.models import User

            return User.objects.none()
        return user.friends.all().order_by("username")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.context["target"]
        request.user.add_friend(target)
        target.add_friend(request.user)
        return Response(
            FriendSerializer(target).data, status=status.HTTP_201_CREATED
        )

    def destroy(self, request, *args, **kwargs):
        # Fetched from the scoped queryset: a non-friend public_id 404s here,
        # so the edge is asserted to belong to request.user before removal.
        friend = self.get_object()
        request.user.remove_friend(friend)
        return Response(status=status.HTTP_204_NO_CONTENT)
