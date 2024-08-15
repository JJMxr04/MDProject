from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from rest_framework.permissions import AllowAny
from rest_framework import status
from core.auth.serializers import RegisterSerializer
from core.auth.models.waitlist import WaitlistEntry
from core.auth.models import email


class RegisterViewSet(ViewSet):
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)
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
            "refresh": 'confirm your email',
            "token": 'confirm your email'
        }, status=status.HTTP_201_CREATED)
