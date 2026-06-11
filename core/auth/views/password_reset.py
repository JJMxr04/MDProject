from django.conf import settings
from django.contrib.auth import views as auth_views
from django.utils.decorators import method_decorator

from core.ratelimit import rate_limit


# Anonymous endpoint that triggers an outbound email per submission — and
# the send is synchronous (Anymail HTTP call inside the request), so an
# unthrottled loop also pins web workers (plan §7.5 item 3).
@method_decorator(rate_limit("auth-pwreset", 5, 3600), name="post")
class BrandedPasswordResetView(auth_views.PasswordResetView):
    """Drop-in PasswordResetView that uses our branded HTML email
    layout. Adds ``site_url`` / ``logo_url`` to the email template
    context so ``email/_base.html`` can render the brand chrome —
    Django's default PasswordResetForm only passes ``protocol`` /
    ``domain`` / ``user`` / ``uid`` / ``token``.
    """
    template_name = 'authorization/password-reset.html'
    email_template_name = 'registration/password_reset_email.txt'
    html_email_template_name = 'registration/password_reset_email.html'
    subject_template_name = 'registration/password_reset_subject.txt'
    extra_email_context = {
        'site_url': settings.SITE_URL,
        'logo_url': settings.EMAIL_LOGO_URL,
    }
