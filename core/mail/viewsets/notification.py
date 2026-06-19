# mail/viewsets.py

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.mail.models import Notification
from core.mail.serializers.notification import NotificationSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user, read=False).order_by('-created_at')

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.read = True
        instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    # @action(detail=False, methods=['patch'])
    # def mark_all_as_read(self, request, *args, **kwargs):
    #     notifications = Notification.objects.filter(user=request.user, read=False)
    #     notifications.update(read=True)
    #     return Response(status=status.HTTP_204_NO_CONTENT)
