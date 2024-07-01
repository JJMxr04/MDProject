from rest_framework import viewsets
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from core.auth.serializers import ActivateSerializer
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from core.auth.serializers import RegisterSerializer
from rest_framework import viewsets, status
from core.user.models import User
from rest_framework.exceptions import ValidationError
from django.shortcuts import render


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
