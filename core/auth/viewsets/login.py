from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from rest_framework.permissions import AllowAny
from rest_framework import status
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from core.auth.serializers import LoginSerializer


class LoginViewSet(ViewSet):
    serializer_class = LoginSerializer
    permission_classes = (AllowAny,)
    http_method_names = ['post']

    def create(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            return Response({"detail": "Invalid token", "message": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        except InvalidToken as e:
            return Response({"detail": "Invalid token", "message": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

        user = serializer.validated_data.get('user')
        if not user:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        print(user)
        if not user.get("activated_link"):
            return Response({"message": "User has not activated their account"}, status=status.HTTP_401_UNAUTHORIZED)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)
