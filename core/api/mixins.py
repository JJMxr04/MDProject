"""Queryset-scoping base (plan 03/04 — AuthZ: scope at the queryset).

``OwnedQuerysetMixin`` is the L3 primary control: a list view can NEVER return
another user's rows because the queryset is filtered to ``request.user`` before
anything else runs. RLS (L5, plan 05) is the backstop under it.

Usage::

    class NotificationViewSet(OwnedQuerysetMixin, V1ViewMixin, ReadOnlyModelViewSet):
        owner_field = "user"
        def get_queryset(self):
            return Notification.objects.all()   # mixin scopes it to the user
"""


class OwnedQuerysetMixin:
    #: the FK on the model that points at the owning user
    owner_field = "user"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user or not user.is_authenticated:
            # Defense in depth — IsAuthenticated should already have 401'd.
            return qs.none()
        return qs.filter(**{self.owner_field: user})
