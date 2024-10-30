from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from django.shortcuts import render, redirect
from django.views import View
from core.user.models import User
from django.http import HttpResponse

class ActivateUserView(View):
    def get(self, request, token, *args, **kwargs):
        if not token:
            return HttpResponse("Token not provided.", status=400)

        try:
            signer = TimestampSigner()
            email = signer.unsign(token, max_age=60 * 60 * 24)  # Token expires after 24 hours
            user = User.objects.get(email=email)
            user.activated_link = True
            user.save()
            return render(request, "activation_email/thank_you.html")
        
        except BadSignature:
            return HttpResponse("Invalid activation link.", status=400)
        
        except SignatureExpired:
            return HttpResponse("Activation link has expired.", status=400)
