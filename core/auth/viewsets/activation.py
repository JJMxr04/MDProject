from rest_framework import viewsets
from rest_framework.response import Response
from django.core.signing import Signer, BadSignature, SignatureExpired
from core.auth.serializers import ActivateSerializer

class ActivateUserViewSet(viewsets.ViewSet):
    def create(self, request):
        serializer = ActivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']

        try:
            signer = Signer()
            email = signer.unsign(token, max_age=60*60*24)  # Token expires after 24 hours
            # Perform activation logic using the 'email' variable
            # (e.g., activate the user account in the database)

            return Response({"detail": "Account activated successfully", "email": email})
        except BadSignature:
            return Response({"detail": "Invalid activation link."}, status=400)
        except SignatureExpired:
            return Response({"detail": "Activation link has expired."}, status=400)
