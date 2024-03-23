from rest_framework.permissions import BasePermission, SAFE_METHODS


class UserPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_anonymous:
            return request.method in SAFE_METHODS

        if view.basename in ["game"]:
            # Check if the user is one of the players in the game
            return request.user == obj.owner or request.user == obj.player_2

        return False

    def has_permission(self, request, view):
        if view.basename in ["game"]:
            if request.user.is_anonymous:
                return request.method in SAFE_METHODS

            return bool(request.user and request.user.is_authenticated)

        return False