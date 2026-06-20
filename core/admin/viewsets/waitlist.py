from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from core.abstract.pagination import AbstractPagination
from core.admin.serializers.waitlist import WaitlistEntryApprovalSerializer, WaitlistEntrySerializer
from core.auth.models.waitlist import WaitlistEntry


class WaitlistEntryViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAdminUser,IsAuthenticated)
    http_method_names = ['get','post']
    queryset = WaitlistEntry.objects.all()
    serializer_class = WaitlistEntrySerializer
    pagination_class = AbstractPagination
    filter_backends = [OrderingFilter, SearchFilter]
    ordering = ['created']
    search_fields = ['email', 'full_name','description','created']

    def get_queryset(self):
        return WaitlistEntry.objects.get_all_waitlist_entries()

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

class WaitlistEntryApprovalViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAdminUser, IsAuthenticated)
    http_method_names = ['post']
    # # queryset = WaitlistEntry.objects.all()
    # serializer_class = WaitlistEntryApprovalSerializer
    # pagination_class = AbstractPagination


    def create(self, request):
        try:
            dataList = request.data
            if not isinstance(dataList, list):
                raise ValueError("Invalid data format. Expected a list.")

            for item in dataList:
                entry = WaitlistEntry.objects.get(id=item.get('id'))
                # Assuming approve_waitlist_entry returns the modified entry
                WaitlistEntry.objects.approve_waitlist_entry(entry.id)

            return Response({'message': 'Request was successful'}, status=status.HTTP_200_OK)
        except WaitlistEntry.DoesNotExist:
            return Response({'message': 'One or more entries not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'message': 'Request was not successful', 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
