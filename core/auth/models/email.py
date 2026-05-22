from django.conf import settings
from django.core.signing import TimestampSigner
from django.urls import reverse

from core.mail.tasks import send_email


def send_activation_email(user, request=None):
    """Enqueue the email-confirmation message via Celery.

    Was previously a synchronous EmailMultiAlternatives().send() that
    hardcoded from_email=os.environ.get('EMAIL_HOST_USER'). That env var
    was retired when the project moved to Resend over HTTPS, so the
    sync send started failing silently. Now it routes through the same
    Celery task every other email uses — picks up the Anymail backend,
    DEFAULT_FROM_EMAIL, retries, logging, and the email/_base.html
    chrome injection.
    """
    signer = TimestampSigner()
    token = signer.sign(user.email)
    url = reverse('core-auth:activate', kwargs={'token': token})

    if request is not None:
        activation_link = request.build_absolute_uri(url)
    else:
        # Fallback for any caller without a request (e.g. mgmt commands).
        activation_link = f"{settings.SITE_URL.rstrip('/')}{url}"

    send_email.delay(
        'Please confirm your registration.',
        user.email,
        'activation_email/activation.html',
        {
            'activation_link': activation_link,
            'username': getattr(user, 'username', '') or '',
        },
    )
