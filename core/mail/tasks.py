import logging
import sys
import traceback

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _stderr(msg):
    print(msg, file=sys.stderr, flush=True)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    soft_time_limit=45,
    time_limit=60,
)
def send_email(self, subject, recipient, template_path, context):
    attempt = self.request.retries + 1
    logger.info(
        "send_email start: attempt=%s to=%s subject=%r template=%s backend=%s host=%s:%s",
        attempt, recipient, subject, template_path,
        settings.EMAIL_BACKEND, settings.EMAIL_HOST, settings.EMAIL_PORT,
    )
    _stderr(f"[send_email] start attempt={attempt} to={recipient} subject={subject!r}")

    try:
        html_content = render_to_string(template_path, context)
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
            "send_email error: attempt=%s to=%s subject=%r exc_type=%s exc=%s",
            attempt, recipient, subject, exc_type, exc,
        )
        _stderr(f"[send_email] ERROR attempt={attempt} to={recipient} {exc_type}: {exc}")
        _stderr(traceback.format_exc())

        if self.request.retries >= self.max_retries:
            logger.error(
                "send_email giving up: to=%s subject=%r after %s attempts",
                recipient, subject, attempt,
            )
            _stderr(f"[send_email] GIVING UP to={recipient} after {attempt} attempts")
            return None
        raise self.retry(exc=exc)
