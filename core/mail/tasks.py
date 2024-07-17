# yourapp/tasks.py

from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import os


@shared_task
def send_email(subject, recipient, template_path, context):
    html_content = render_to_string(template_path, context)
    text_content = strip_tags(html_content)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=os.environ.get('EMAIL_HOST_USER'),
        to=[recipient],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()
