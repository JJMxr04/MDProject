from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from core.auth.models.waitlist import WaitlistEntry
from core.admin.serializers.waitlist import WaitlistEntrySerializer

class WaitlistEntryViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAdminUser,IsAuthenticated)
    http_method_names = ['get','patch']
    queryset = WaitlistEntry.objects.all()
    serializer_class = WaitlistEntrySerializer

    def get_queryset(self):
        return WaitlistEntry.objects.get_all_wailtlist_entries()

    def get_object(self):
        obj = WaitlistEntry.objects.get_object_by_public_id(self.kwargs['pk'])

        self.check_object_permissions(self.request, obj)

        return obj

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):

        entry = WaitlistEntry.objects.get_object_by_id(kwargs['pk'])
        entry = WaitlistEntry.objects.approve_waitlist_entry(entry.id)
        serializer = self.get_serializer(entry)
        return Response(serializer.data)