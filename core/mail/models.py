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

    @classmethod
    def send_tournament_invite(cls, user, tournament):
        subject = f"You're Invited to Join the {tournament.name} Tournament!"
        recipient = [user.email]
        template_path = "tournamentInvite/tournamentInvite.html"

        context = {
            'tournament_name': tournament.name,
            'username': user.name,
            'tournament_date': tournament.start_date.strftime('%B %d, %Y'),
            'tournament_location': 'Tournament Location',  # Replace with actual location if available
            # 'tournament_prize': 'Tournament Prize',  # Uncomment if prize information is available
            # 'registration_link': 'Registration Link',  # Uncomment if registration link is available
            # 'support_url': 'Support URL',  # Uncomment if support URL is available
        }

        # Render the HTML content of the email template with context
        html_content = render_to_string(template_path, context)

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

    @classmethod
    def send_waitlist_granted(cls, email):
        subject = "Thank You for Signing Up for the Waitlist"
        recipient = [email]
        template_path = "waitlist/waitlist_granted.html"

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
