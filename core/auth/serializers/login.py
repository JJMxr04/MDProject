from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings

from core.user.models import User
from core.user.serializers import UserSerializer


class LoginSerializer(TokenObtainPairSerializer):
    portal_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'portal_password']

    def validate(self, attrs):
        # Print the attributes for debugging

        # Extract the email and portal_password from the incoming data
        email = attrs.get('email')
        portal_password = attrs.get('portal_password')

        # Authenticate using the custom field portal_password
        user = authenticate(request=self.context.get('request'),
                            username=email, portal_password=portal_password)

        # Check if the user is authenticated
        if user is None:
            raise serializers.ValidationError('Invalid credentials')

        # Get token for the authenticated user
        refresh = self.get_token(user)

        # Prepare the response data
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        }

        # Update the last login time of the user
        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, user)

        return data
