import logging
import sys
import traceback

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from procrastinate import RetryStrategy
from procrastinate.contrib.django import app

from core import timeprefs

logger = logging.getLogger(__name__)


def _stderr(msg):
    print(msg, file=sys.stderr, flush=True)


def recipient_time_context(recipient):
    """Activate the recipient's stored timezone + clock format for the email
    render, so every ``|usertime`` in the body comes out in their zone/clock.

    Resolves prefs by recipient email — no call-site changes needed, every
    email auto-localizes. Unknown address (or non-user recipient) → UTC / 12h.
    Always restored on exit (try/finally in time_context) so a worker thread
    never carries one recipient's zone into the next job (Security H3).
    """
    from core.user.models import User

    prefs = (
        User.objects.filter(email=recipient)
        .values_list("timezone", "clock_format")
        .first()
    )
    tz, clock = prefs if prefs else (timeprefs.DEFAULT_TIMEZONE,
                                     timeprefs.DEFAULT_CLOCK_FORMAT)
    return timeprefs.time_context(tz, clock)


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
        # Render inside the recipient's timezone/clock so every |usertime in
        # the template localizes to them (spec §5 — emails are in scope).
        with recipient_time_context(recipient):
            html_content = render_to_string(template_path, ctx)
        text_content = strip_tags(html_content)

        # RFC 8058 one-click unsubscribe headers — Gmail/Yahoo require them
        # for bulk-ish senders, and they keep the Resend domain reputation
        # healthy. Present whenever the caller routed through
        # Emails._notify (engagement mail); absent on transactional mail.
        headers = {}
        unsubscribe_url = ctx.get("unsubscribe_url")
        if unsubscribe_url:
            headers["List-Unsubscribe"] = f"<{unsubscribe_url}>"
            headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
            headers=headers,
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
