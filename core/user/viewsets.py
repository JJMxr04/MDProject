from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.abstract.viewsets import AbstractViewSet
from core.user.models import User
from core.user.serializers import PublicUserSerializer, UserMeSerializer, UserSerializer


class UserViewSet(AbstractViewSet):
    http_method_names = ('patch', 'get')
    permission_classes = (IsAuthenticated,)
    serializer_class = PublicUserSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return User.objects.all()
        return User.objects.exclude(is_superuser=True)

    def get_object(self):
        obj = User.objects.get_object_by_public_id(self.kwargs['pk'])

        self.check_object_permissions(self.request, obj)
        return obj

class UserMeViewSet(viewsets.ViewSet):
    http_method_names = ('patch', 'get')
    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication,)
    parser_classes = (MultiPartParser, FormParser)  # Ensure multipart data is parsed
    serializer_class = UserMeSerializer

    def retrieve(self, request):
        # Get the current user's data
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def partial_update(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

