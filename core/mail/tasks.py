import logging
import sys
import traceback

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from procrastinate import RetryStrategy
from procrastinate.contrib.django import app

logger = logging.getLogger(__name__)


def _stderr(msg):
    print(msg, file=sys.stderr, flush=True)


# Procrastinate equivalent of Celery's max_retries=3, default_retry_delay=30.
# linear_wait=30 means: retry after 30s, then 60s, then 90s. Total 3 retries
# before the job is marked failed. Raising any exception triggers a retry;
# Procrastinate handles the rescheduling.
@app.task(
    name="core.mail.send_email",
    queue="default",
    retry=RetryStrategy(max_attempts=3, linear_wait=30),
)
def send_email(subject, recipient, template_path, context):
    logger.info(
        "send_email start: to=%s subject=%r template=%s backend=%s from=%s",
        recipient, subject, template_path,
        settings.EMAIL_BACKEND, settings.DEFAULT_FROM_EMAIL,
    )
    _stderr(f"[send_email] start to={recipient} subject={subject!r}")

    try:
        # Inject brand chrome into every email so templates can build
        # absolute URLs (logo, links). Caller-provided context wins.
        ctx = {
            "site_url": settings.SITE_URL,
            "logo_url": settings.EMAIL_LOGO_URL,
            "subject": subject,
            **(context or {}),
        }
        html_content = render_to_string(template_path, ctx)
        text_content = strip_tags(html_content)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        email.attach_alternative(html_content, "text/html")
        sent = email.send(fail_silently=False)

        logger.info("send_email ok: to=%s subject=%r sent=%s", recipient, subject, sent)
        _stderr(f"[send_email] ok to={recipient} sent={sent}")
        return sent

    except Exception as exc:
        exc_type = type(exc).__name__
        logger.exception(
            "send_email error: to=%s subject=%r exc_type=%s exc=%s",
            recipient, subject, exc_type, exc,
        )
        _stderr(f"[send_email] ERROR to={recipient} {exc_type}: {exc}")
        _stderr(traceback.format_exc())
        raise
