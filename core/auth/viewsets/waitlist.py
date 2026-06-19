from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.api.throttling import AuthSensitiveRateThrottle
from core.auth.models.waitlist import WaitlistEntry
from core.auth.serializers.waitlist import WaitlistEntrySerializer


# NOTE: not currently routed (core/routers.py registration is commented
# out) — the live signup flow is the /auth/waitlist/ form view. Hardened
# anyway so re-enabling the route doesn't resurrect the holes: the old
# create() passed registered/activated/admin_granted_access straight from
# client data, letting an anonymous caller self-approve past the waitlist
# gate, and its duplicate-email error confirmed list membership.
class WaitlistEntryViewSet(viewsets.ModelViewSet):
    permission_classes = (AllowAny,)
    throttle_classes = (AuthSensitiveRateThrottle,)
    http_method_names = ['post']
    queryset = WaitlistEntry.objects.all()
    serializer_class = WaitlistEntrySerializer

    def create(self, request, *args, **kwargs):
        email = request.data.get('email', None)
        if email and WaitlistEntry.objects.filter(email__iexact=email).exists():
            # Same response as a fresh signup — don't leak list membership.
            return Response({'detail': "You're on the waitlist."}, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Privileged flags are NEVER client-settable on a public endpoint.
            WaitlistEntry.objects.create_entry(
                email=email,
                full_name=request.data.get('full_name', ''),
                description=request.data.get('description', ''),
            )
            return Response({'detail': "You're on the waitlist."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
