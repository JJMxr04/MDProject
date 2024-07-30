from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from core.auth.models.waitlist import WaitlistEntry
from core.auth.serializers.waitlist import WaitlistEntrySerializer
from core.mail.models import Emails

class WaitlistEntryViewSet(viewsets.ModelViewSet):
    permission_classes = (AllowAny,)
    http_method_names = ['post']
    queryset = WaitlistEntry.objects.all()
    serializer_class = WaitlistEntrySerializer

    def create(self, request, *args, **kwargs):
        email = request.data.get('email', None)
        if email:
            existing_entry = WaitlistEntry.objects.filter(email=email).first()
            if existing_entry and not existing_entry.admin_granted_access:
                return Response({'detail': 'An entry with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        print(request.data)
        print(serializer.is_valid())
        if serializer.is_valid():
            # Create the entry using the custom manager method
            entry = WaitlistEntry.objects.create_entry(
                email=email,
                full_name=request.data.get('full_name', ''),
                description=request.data.get('description', ''),
                registered=request.data.get('registered', False),
                activated=request.data.get('activated', False),
                admin_granted_access=request.data.get('admin_granted_access', False)
            )
            # Serialize the created entry
            serialized_entry = WaitlistEntrySerializer(entry)
            Emails.send_waitlist_thank_you(email=email) # Sending an email
            return Response(serialized_entry.data, status=status.HTTP_200_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
