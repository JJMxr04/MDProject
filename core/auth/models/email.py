from core.mail import views
from django.urls import reverse
from django.core.signing import Signer
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import os
from django.utils.crypto import salted_hmac
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature


def send_activation_email(user, request):
    # Generate a signed token using Django's signing mechanism
    signer = TimestampSigner()
    token = signer.sign(user.email)

    url_pattern_name = 'core-auth:activate'
    url = reverse(url_pattern_name, kwargs={'token': token}).lstrip('/')

    link = request.build_absolute_uri('/') + url  # or your specific domain

    subject = 'Please confirm your registration.'
    rec = [user.email]
    template_path = "activation_email/activation.html"

    html_content = render_to_string(template_path, {'activation_link': link})

    text_content = strip_tags(html_content)

    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=os.environ.get('EMAIL_HOST_USER'),
        to=rec,
    )

    email_message.attach_alternative(html_content, "text/html")

    # Send the email using Django's email sending functions
    email_message.send()

