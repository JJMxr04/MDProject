import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_email(self, subject, recipient, template_path, context):
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
        return sent
    except Exception as exc:
        logger.exception("send_email failed: to=%s subject=%r", recipient, subject)
        raise self.retry(exc=exc)
