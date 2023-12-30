from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from core.event.serializers.event import EventSerializer
from core.event.models.event import Event
from core.event.pagination.pagination import EventPagination
from core.abstract.viewsets import AbstractViewSet
from rest_framework.response import Response


class EventViewSet(AbstractViewSet):
    http_method_names = 'get'
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = EventSerializer
    queryset = Event.objects.all()
    ordering = ['-commence_time']
    # ordering = []
    pagination_class = EventPagination  # Use the custom pagination class

    def get_queryset(self):
        return Event.objects.get_active_events()

    def get_object(self):
        obj = Event.objects.get_object_by_public_id(self.kwargs['pk'])

        self.check_object_permissions(self.request, obj)

        return obj

