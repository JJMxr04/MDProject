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

        send_email.delay(subject, email, template_path, context)

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

        send_email.delay(subject, user.email, template_path, context)

    # Similarly refactor other methods in the Emails class

    @classmethod
    def send_waitlist_granted(cls, email):
        subject = "Your Waitlist Request Has Been Granted"
        template_path = "waitlist/waitlist_granted.html"
        context = {}

        send_email.delay(subject, email, template_path, context)

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

        send_email.delay(subject, user.email, template_path, context)


    @classmethod
    def send_opponent_pick_notification(cls, user, opponent_name):

        subject = f"Your Opponent {opponent_name} Has Uploaded a Pick"
        template_path = "game/upload.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        Notification.objects.create_notification(user,subject)

        send_email.delay(subject, user.email, template_path, context)

    @classmethod
    def send_match_victory_notification(cls, user, opponent_name):

        subject = "Congratulations, You Won the Match!"
        template_path = "match/matchVictory.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        Notification.objects.create_notification(user,subject)
        send_email.delay(subject, user.email, template_path, context)

    @classmethod
    def send_match_tie_notification(cls, user, opponent_name):
        subject = "Your Match Ended in a Tie"
        template_path = "match/matchTie.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        Notification.objects.create_notification(user,subject)


        send_email.delay(subject, user.email, template_path, context)

    @classmethod
    def send_match_lost_notification(cls, user, opponent_name):
        subject = "Match Result: You Lost"
        template_path = "match/matchLost.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        Notification.objects.create_notification(user,subject)

        send_email.delay(subject, user.email, template_path, context)

    @classmethod
    def send_tournament_victory_notification(cls, user, tournament):

        subject = f"Congratulations! You Won the {tournament.name} Tournament!"
        template_path = "tournament/tournamentVictory.html"
        context = {
            'tournament_name': tournament.name,
            'username': user.username,
        }
        Notification.objects.create_notification(user,subject)

        send_email.delay(subject, user.email, template_path, context)

    @classmethod
    def send_tournament_starting_notification(cls, user, tournament):

        subject = f"The {tournament.name} Tournament Starts in 2 Days!"
        template_path = "tournamentInvite/tournamentStartingNotification.html"
        context = {
            'tournament_name': tournament.name,
            'username': user.username,
            'tournament_date': tournament.start_date.strftime('%B %d, %Y'),
            'tournament_location': 'Tournament Location',
        }
        Notification.objects.create_notification(user,subject)

        send_email.delay(subject, user.email, template_path, context)

    @classmethod
    def send_match_invite(cls, user, opponent_name):
        subject = "Your have Been Invited to Join a Match"
        template_path = "invite/matchInvite.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        Notification.objects.create_notification(user,subject)
        send_email.delay(subject, user.email, template_path, context)

    @classmethod
    def send_match_invite(cls, user, opponent_name):
        subject = "Your have Been Invited to Join a Tournament"
        template_path = "invite/tournamentInvite.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        Notification.objects.create_notification(user,subject)
        send_email.delay(subject, user.email, template_path, context)

    

