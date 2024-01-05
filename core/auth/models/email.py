from core.mail import views
from django.urls import reverse
from django.core.signing import Signer
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_activation_email( to):
    # Generate a signed token using Django's signing mechanism
    signer = Signer()
    # token = signer.sign(user.email)
    token = signer.sign(to)
    subject = 'Please confirm your registration.'
    url_pattern_name = 'activate'
    url = reverse(url_pattern_name, kwargs={'token': token})

    template_path = "auth/templates/activation.html"
    html_content = render_to_string(template_path, {'activation_link': url})
    text_content = strip_tags(html_content)
    email_message = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=to,
        to=to,
    )

    email_message.attach_alternative(html_content, "text/html")

    # Send the email using Django's email sending functions
    email_message.send()

