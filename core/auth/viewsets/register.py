from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from core.api.throttling import AuthSensitiveRateThrottle
from core.auth.models import email
from core.auth.models.waitlist import WaitlistEntry
from core.auth.serializers import RegisterSerializer


# NOTE: not currently routed (core/routers.py registration is commented
# out) — the live flow is the /auth/register/ form view. Throttled anyway
# so re-enabling the route doesn't expose an unthrottled approval-status
# probe + activation-email sender.
class RegisterViewSet(ViewSet):
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)
    throttle_classes = (AuthSensitiveRateThrottle,)
    http_method_names = ['post']

    def create(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_temp = serializer.validated_data

        # Check if admin has granted access
        if WaitlistEntry.objects.filter(email=user_temp.get('email'), admin_granted_access=True).exists():
            # If admin has granted access, set activated to True
            WaitlistEntry.objects.filter(email=user_temp.get('email')).update(activated=True)
        else:
            return Response({"detail": "You have not been approved to register"}, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        email.send_activation_email(user, request)

        return Response({
            "user": serializer.data,
            "refresh": 'confirm your email',  # nosec B105 -- human-readable placeholder, not a credential
            "token": 'confirm your email'  # nosec B105 -- human-readable placeholder, not a credential
        }, status=status.HTTP_201_CREATED)
