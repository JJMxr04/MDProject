from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.shortcuts import render
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.auth.serializers import ActivateSerializer, RegisterSerializer
from core.user.models import User


class ActivateUserViewSet(viewsets.ViewSet):
    serializer_class = ActivateSerializer
    permission_classes = (AllowAny,)
    http_method_names = ['get']

    def retrieve(self, request, *args, **kwargs):
        token = kwargs.get('token')

        if not token:
            return Response({"detail": "Token not provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            signer = TimestampSigner()
            email = signer.unsign(token, max_age=60 * 60 * 24)  # Token expires after 24 hours
            user = User.objects.get(email=email)
            user.activated_link = True
            user.save()

            # return Response({"detail": "Account activated successfully", "email": email})
            return render(request,"activation_email/thank_you.html")
        except BadSignature:
            return Response({"detail": "Invalid activation link."}, status=status.HTTP_400_BAD_REQUEST)
        except SignatureExpired:
            return Response({"detail": "Activation link has expired."}, status=status.HTTP_400_BAD_REQUEST)
    #
