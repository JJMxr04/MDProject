from rest_framework.permissions import IsAuthenticated
from core.user.serializers import UserSerializer
from core.user.models import User
from core.abstract.viewsets import AbstractViewSet
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from rest_framework import viewsets


class UserViewSet(AbstractViewSet):
    http_method_names = ('patch', 'get')
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return User.objects.all()
        return User.objects.exclude(is_superuser=True)

    def get_object(self):
        obj = User.objects.get_object_by_public_id(self.kwargs['pk'])

        self.check_object_permissions(self.request, obj)
        return obj

class AdminUserViewSet(viewsets.ViewSet):
    permission_classes = (IsAdminUser,)

    def make_user_staff(self, request, pk):
        user = User.objects.get_object_by_public_id(pk)
        if user:
            User.objects.make_user_staff(user)
            return Response({"message": "User is now staff."}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    def make_user_admin(self, request, pk):
        user = User.objects.get_object_by_public_id(pk)
        if user:
            User.objects.make_user_admin(user)
            return Response({"message": "User is now admin."}, status=status.HTTP_200_OK)
        else:
            return Response({"message": "User not found."}, status=status.HTTP_404_NOT_FOUND)

