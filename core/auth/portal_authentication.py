from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

UserModel = get_user_model()

class PortalPasswordBackend(BaseBackend):
    def authenticate(self, request, username=None, portal_password=None, **kwargs):
        if username is None or portal_password is None:
            return None
        try:
            user = UserModel.objects.get(email=username)
        except UserModel.DoesNotExist:
            return None
        if user.check_portal_password(portal_password) and self._user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None

    def _user_can_authenticate(self, user):
        """
        This method is used to check if the user can authenticate.
        It should ensure the user is active, by default Django's ModelBackend has this method.
        """
        is_active = getattr(user, 'is_active', None)
        return is_active or is_active is None
