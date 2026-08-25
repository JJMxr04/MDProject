"""``/api/v1/notifications/`` — pilot island.

The lowest-blast-radius page, used to prove the secure pattern end to end:

- **List** (`GET /api/v1/notifications/`) — scoped by `OwnedQuerysetMixin`, so it
  can NEVER return another user's rows (L3 primary control).
- **Count** (`GET /api/v1/notifications/count/`) — the badge number; the count of
  the requester's notifications (reading/clearing deletes them, so all that
  remain are unread).
- **Mark read** (`PATCH /api/v1/notifications/<id>/`) and **Clear**
  (`POST /api/v1/notifications/<id>/clear/`) — fetched from the scoped queryset
  (a non-owned id 404s before anything runs — existence not leaked). Reading or
  clearing a notification deletes it outright.
- **Mark all read / Clear all** (`POST .../mark-all-read/`, `POST .../clear-all/`)
  — delete every notification the requester owns.

Object-level safety is doubly enforced: the scoped `get_queryset` 404s non-owned
ids, and `IsRecipient` is declared as a belt-and-braces object permission. Session
auth enforces CSRF on these unsafe methods.
"""

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.api.base import V1ViewMixin
from core.api.mixins import OwnedQuerysetMixin
from core.api.permissions import IsRecipient
from core.mail.models import Notification
from core.mail.serializers.notification import NotificationV1Serializer


class NotificationViewSet(
    OwnedQuerysetMixin,
    V1ViewMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = NotificationV1Serializer
    permission_classes = V1ViewMixin.permission_classes + [IsRecipient]
    owner_field = "user"
    # OwnedQuerysetMixin.get_queryset() filters this to request.user.
    queryset = Notification.objects.all().order_by("-created_at")

    @action(detail=False, methods=["get"])
    def count(self, request):
        """Badge count — the requester's notifications (reading/clearing deletes
        them, so the remaining rows are exactly the unread set)."""
        return Response({"count": Notification.objects.unread(request.user).count()})

    def partial_update(self, request, *args, **kwargs):
        """Mark read — deletes the notification."""
        notification = self.get_object()  # 404 for a non-owned id (scoped qs)
        notification.mark_read()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def clear(self, request, *args, **kwargs):
        """Clear — deletes the notification."""
        notification = self.get_object()  # 404 for a non-owned id (scoped qs)
        notification.clear()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        """Delete every notification the requester owns."""
        result = Notification.objects.mark_all_read(request.user)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="clear-all")
    def clear_all(self, request):
        """Delete every notification the requester owns."""
        result = Notification.objects.clear_all(request.user)
        return Response(result, status=status.HTTP_200_OK)
