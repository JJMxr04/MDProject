# yourapp/emails.py

from core.mail.tasks import send_email

from core.mail.models.notifications import Notification
import os


class Emails:
    @classmethod
    def send_waitlist_thank_you(cls, email):
        subject = "Thank You for Signing Up for the Waitlist"
        template_path = "waitlist/waitlist_thank_you.html"
        context = {}

        send_email.defer(subject=subject, recipient=email, template_path=template_path, context=context)

    @classmethod
    def send_tournament_invite(cls, user, tournament):
        subject = f"You're Invited to Join the {tournament.name} Tournament!"
        template_path = "tournament/tournamentInvite/tournamentInvite.html"
        context = {
            'tournament_name': tournament.name,
            'username': user.username,
            'tournament_date': tournament.start_date.strftime('%B %d, %Y'),
            'tournament_location': 'Tournament Location',
        }
        Notification.objects.create_notification(user,subject)

        send_email.defer(subject=subject, recipient=user.email, template_path=template_path, context=context)

    # Similarly refactor other methods in the Emails class

    @classmethod
    def send_waitlist_granted(cls, email):
        subject = "Your Waitlist Request Has Been Granted"
        template_path = "waitlist/waitlist_granted.html"
        context = {}

        send_email.defer(subject=subject, recipient=email, template_path=template_path, context=context)

    @classmethod
    def send_tournament_acceptance_confirmation(cls, user, tournament):
        subject = f"You Have Accepted the Invite for the {tournament.name} Tournament!"
        template_path = "tournament/tournamentInvite/tournamentAcceptance.html"
        context = {
            'tournament_name': tournament.name,
            'username': user.username,
            'tournament_date': tournament.start_date.strftime('%B %d, %Y'),
            'tournament_location': 'Tournament Location',
        }
        Notification.objects.create_notification(user,subject)

        send_email.defer(subject=subject, recipient=user.email, template_path=template_path, context=context)


    @classmethod
    def send_opponent_pick_notification(cls, user, opponent_name):

        subject = f"Your Opponent {opponent_name} Has Uploaded a Pick"
        template_path = "game/upload.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        Notification.objects.create_notification(user,subject)

        send_email.defer(subject=subject, recipient=user.email, template_path=template_path, context=context)

    @classmethod
    def send_match_victory_notification(cls, user, opponent_name):

        subject = "Congratulations, You Won the Match!"
        template_path = "match/matchVictory.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        Notification.objects.create_notification(user,subject)
        send_email.defer(subject=subject, recipient=user.email, template_path=template_path, context=context)

    @classmethod
    def send_match_tie_notification(cls, user, opponent_name):
        subject = "Your Match Ended in a Tie"
        template_path = "match/matchTie.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        Notification.objects.create_notification(user,subject)


        send_email.defer(subject=subject, recipient=user.email, template_path=template_path, context=context)

    @classmethod
    def send_match_lost_notification(cls, user, opponent_name):
        subject = "Match Result: You Lost"
        template_path = "match/matchLost.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        Notification.objects.create_notification(user,subject)

        send_email.defer(subject=subject, recipient=user.email, template_path=template_path, context=context)

    @classmethod
    def send_tournament_victory_notification(cls, user, tournament):

        subject = f"Congratulations! You Won the {tournament.name} Tournament!"
        template_path = "tournament/tournamentVictory.html"
        context = {
            'tournament_name': tournament.name,
            'username': user.username,
        }
        Notification.objects.create_notification(user,subject)

        send_email.defer(subject=subject, recipient=user.email, template_path=template_path, context=context)

    @classmethod
    def send_tournament_starting_notification(cls, user, tournament):

        subject = f"The {tournament.name} Tournament Starts in 2 Days!"
        template_path = "tournament/tournamentStartsIn2Days.html"
        context = {
            'tournament_name': tournament.name,
            'username': user.username,
            'tournament_date': tournament.start_date.strftime('%B %d, %Y'),
            'tournament_location': 'Tournament Location',
        }
        Notification.objects.create_notification(user,subject)

        send_email.defer(subject=subject, recipient=user.email, template_path=template_path, context=context)

    @classmethod
    def send_match_invite(cls, user, opponent_name):
        subject = "Your have Been Invited to Join a Match"
        template_path = "invite/matchInvite.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        Notification.objects.create_notification(user,subject)
        send_email.defer(subject=subject, recipient=user.email, template_path=template_path, context=context)

    @classmethod
    def send_match_acceptance_confirmation(cls, user, opponent_name):
        """Sender-side: the user who SENT the invite gets notified that
        their opponent accepted. ``user`` is the sender; ``opponent_name``
        is the accepter's username.
        """
        subject = f"{opponent_name} accepted your match invite — you're now in a match!"
        template_path = "invite/matchAccept.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        Notification.objects.create_notification(user, subject)
        send_email.defer(subject=subject, recipient=user.email, template_path=template_path, context=context)

    @classmethod
    def send_match_started_to_accepter(cls, user, opponent_name):
        """Accepter-side: the user who just ACCEPTED an invite gets
        confirmation that the match is on. ``user`` is the accepter;
        ``opponent_name`` is the sender's username.
        """
        subject = f"You're now in a match with {opponent_name}"
        template_path = "invite/matchAccepted.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        Notification.objects.create_notification(user, subject)
        send_email.defer(subject=subject, recipient=user.email, template_path=template_path, context=context)






    

