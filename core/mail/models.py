# Assuming this code is in a file like core/mail.py

from django.db import models
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import os

class Emails:
    @classmethod
    def send_waitlist_thank_you(cls, email):
        subject = "Thank You for Signing Up for the Waitlist"
        recipient = [email]
        template_path = "waitlist/waitlist_thank_you.html"

        # Render the HTML content of the email template
        html_content = render_to_string(template_path)

        # Strip the HTML tags to create a plaintext version of the email
        text_content = strip_tags(html_content)

        # Create EmailMultiAlternatives object
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=os.environ.get('EMAIL_HOST_USER'),  # Sender's email
            to=recipient,  # Recipient's email
        )

        # Attach the HTML content as email body
        email.attach_alternative(html_content, "text/html")

        # Send email
        email.send()