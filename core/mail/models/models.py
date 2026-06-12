# yourapp/emails.py

from django.db import transaction

from procrastinate import exceptions as procrastinate_exceptions

from core.mail.tasks import send_email

from core.mail.models.notifications import Notification
import os


class Emails:
    @classmethod
    def _notify(cls, user, subject, template_path, context, dedupe_key=None):
        """Single chokepoint for user-facing engagement notifications.

        Always writes the in-app Notification row; only sends the email if
        the user hasn't opted out (``User.email_notifications``). Every
        email carries an unsubscribe link in its context so ``_base.html``
        can render the footer link and the task can set the
        ``List-Unsubscribe`` header.

        ``dedupe_key`` maps to a Procrastinate queueing lock: while a job
        holding the key is still queued, a second defer with the same key
        is silently dropped — concurrent settlement paths can't double-send
        the same result email. The inner atomic() is a savepoint so the
        lock violation can't poison a caller's open transaction.

        Transactional mail (account activation, password reset, waitlist)
        does NOT route through here and ignores the preference.
        """
        Notification.objects.create_notification(user, subject)

        if not getattr(user, "email_notifications", True):
            return

        from core.mail.unsubscribe import unsubscribe_url

        context = {**(context or {}), "unsubscribe_url": unsubscribe_url(user)}
        deferrer = (
            send_email.configure(queueing_lock=dedupe_key)
            if dedupe_key else send_email
        )
        try:
            with transaction.atomic():
                deferrer.defer(
                    subject=subject,
                    recipient=user.email,
                    template_path=template_path,
                    context=context,
                )
        except procrastinate_exceptions.AlreadyEnqueued:
            pass

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
        cls._notify(user, subject, template_path, context)

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
        cls._notify(user, subject, template_path, context)

    @classmethod
    def send_opponent_pick_notification(cls, user, opponent_name):

        subject = f"Your Opponent {opponent_name} Has Uploaded a Pick"
        template_path = "game/upload.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        cls._notify(user, subject, template_path, context)

    @classmethod
    def send_pick_summary(cls, user, opponent_name, pick_count):
        """Coalesced replacement for per-pick notifications — one summary
        per debounce window (see ``core.game.tasks.send_pick_summary``)."""
        if pick_count == 1:
            subject = f"{opponent_name} made a pick in your match"
        else:
            subject = f"{opponent_name} has made {pick_count} picks in your match"
        template_path = "game/pick_summary.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
            'pick_count': pick_count,
        }
        cls._notify(user, subject, template_path, context)

    @classmethod
    def send_match_victory_notification(cls, user, opponent_name, match_id=None):

        subject = "Congratulations, You Won the Match!"
        template_path = "match/matchVictory.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        cls._notify(
            user, subject, template_path, context,
            dedupe_key=f"match-result-{match_id}-{user.pk}" if match_id else None,
        )

    @classmethod
    def send_match_tie_notification(cls, user, opponent_name, match_id=None):
        subject = "Your Match Ended in a Tie"
        template_path = "match/matchTie.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        cls._notify(
            user, subject, template_path, context,
            dedupe_key=f"match-result-{match_id}-{user.pk}" if match_id else None,
        )

    @classmethod
    def send_match_lost_notification(cls, user, opponent_name, match_id=None):
        subject = "Match Result: You Lost"
        template_path = "match/matchLost.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        cls._notify(
            user, subject, template_path, context,
            dedupe_key=f"match-result-{match_id}-{user.pk}" if match_id else None,
        )

    @classmethod
    def send_tournament_victory_notification(cls, user, tournament):

        subject = f"Congratulations! You Won the {tournament.name} Tournament!"
        template_path = "tournament/tournamentVictory.html"
        context = {
            'tournament_name': tournament.name,
            'username': user.username,
        }
        cls._notify(user, subject, template_path, context)

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
        cls._notify(user, subject, template_path, context)

    @classmethod
    def send_match_invite(cls, user, opponent_name):
        subject = "Your have Been Invited to Join a Match"
        template_path = "invite/matchInvite.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
        }
        cls._notify(user, subject, template_path, context)

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
        cls._notify(user, subject, template_path, context)

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
        cls._notify(user, subject, template_path, context)
