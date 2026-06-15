"""Object-level permissions for the v1 surface (plan 03/04 — AuthZ).

Deny by default. Lists are scoped at the queryset (``OwnedQuerysetMixin``);
detail/update/delete add one of these object-level checks AND fetch the object
from the scoped queryset, so a non-owned id 404s before the permission runs
(404-not-403 existence hiding).

These mirror the intent of the existing function-view decorators in
``core/match/decorators/`` (``player_in_match_required`` -> ``IsPlayerInMatch``).
"""

from rest_framework.permissions import BasePermission

from core.billing.entitlement import user_can_access_analytics


class IsPaid(BasePermission):
    """Requester is PRO-entitled.

    Mirrors the portal ``@require_paid`` gate: defers to
    ``user_can_access_analytics`` (the user's Subscription entitlement).
    Currently unapplied — analytics is free (Phase 16/D-16d); this is the
    gate for the opponent-scouting endpoint (Phase 9).
    """

    def has_permission(self, request, view):
        return user_can_access_analytics(request.user)


class IsOwner(BasePermission):
    """``obj.<owner_field> == request.user`` (default field ``user``).

    Override the field per-view with ``owner_field`` on the view class.
    """

    owner_field = "user"

    def has_object_permission(self, request, view, obj):
        owner_field = getattr(view, "owner_field", self.owner_field)
        return getattr(obj, owner_field, None) == request.user


class IsRecipient(BasePermission):
    """Notification / invite: ``obj.user`` is the recipient."""

    def has_object_permission(self, request, view, obj):
        return getattr(obj, "user", None) == request.user


class IsPlayerInMatch(BasePermission):
    """Requester is one of the two players.

    Handles both ``Match`` (``player_1`` / ``player_2``) and ``Game``
    (``owner`` / ``player_2``) objects — the same two-sided membership the
    ``player_in_match_required`` / ``player_in_game_required`` decorators enforce.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        if hasattr(obj, "player_1"):
            return user == obj.player_1 or user == getattr(obj, "player_2", None)
        if hasattr(obj, "owner"):
            return user == obj.owner or user == getattr(obj, "player_2", None)
        return False


class IsParticipant(BasePermission):
    """Tournament: requester is enrolled (``tournament.players__player``)."""

    def has_object_permission(self, request, view, obj):
        players = getattr(obj, "players", None)
        if players is not None and hasattr(players, "filter"):
            return players.filter(player=request.user).exists()
        return False
