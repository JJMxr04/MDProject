"""``/api/v1/notifications/`` — Phase 1 pilot island (plan 07/10).

The lowest-blast-radius page, used to prove the secure pattern end to end:

- **List** (`GET /api/v1/notifications/`) — scoped by `OwnedQuerysetMixin`, so it
  can NEVER return another user's rows (L3 primary control).
- **Count** (`GET /api/v1/notifications/count/`) — the badge number.
- **Mark read** (`PATCH /api/v1/notifications/<id>/`) — fetched from the scoped
  queryset (a non-owned id 404s before anything runs — existence not leaked) and
  deleted via the owner-scoped `Notification.objects.mark_read` (S-13). Session
  auth enforces CSRF on this unsafe method.

Object-level safety is doubly enforced: the scoped `get_queryset` 404s non-owned
ids, and `IsRecipient` is declared as a belt-and-braces object permission.
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
        """Badge count — number of the requester's own notifications."""
        return Response({"count": self.get_queryset().count()})

    def partial_update(self, request, *args, **kwargs):
        """Mark read = delete (this app has no read flag; see S-13)."""
        notification = self.get_object()  # 404 for a non-owned id (scoped qs)
        Notification.objects.mark_read(notification.id, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
