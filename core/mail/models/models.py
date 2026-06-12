# yourapp/emails.py

from django.db import transaction

from procrastinate import exceptions as procrastinate_exceptions

from core.mail.tasks import send_email

from core.mail.models.notifications import Notification
import os


class Emails:
    @staticmethod
    def _match_url(match_id):
        """Absolute URL of the match detail page — result emails link it so
        the rematch CTA (Phase 5 §5) is one click away."""
        if not match_id:
            return None
        from django.conf import settings
        from django.urls import reverse
        return settings.SITE_URL + reverse(
            'core-portal:portal-my-match-detail', args=[match_id],
        )

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
            'match_url': cls._match_url(match_id),
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
            'match_url': cls._match_url(match_id),
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
            'match_url': cls._match_url(match_id),
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
    def send_match_invite(cls, user, opponent_name, format_label=None):
        subject = "Your have Been Invited to Join a Match"
        template_path = "invite/matchInvite.html"
        context = {
            'username': user.username,
            'opponent_name': opponent_name,
            'format_label': format_label,
        }
        cls._notify(user, subject, template_path, context)

    @classmethod
    def send_friend_invite(cls, user, sender_name):
        subject = f"{sender_name} sent you a friend request"
        template_path = "invite/friendInvite.html"
        context = {
            'username': user.username,
            'sender_name': sender_name,
        }
        cls._notify(user, subject, template_path, context)

    @classmethod
    def send_invite_declined(cls, user, decliner_name, invite_type):
        """Sender-side: the user who SENT the invite learns it was declined
        (Phase 4 §2 — decline used to be silent). ``user`` is the sender."""
        noun = "friend request" if invite_type == 'friend' else f"{invite_type} invite"
        subject = f"{decliner_name} declined your {noun}"
        template_path = "invite/inviteDeclined.html"
        context = {
            'username': user.username,
            'decliner_name': decliner_name,
            'invite_noun': noun,
        }
        cls._notify(user, subject, template_path, context)

    @classmethod
    def send_signup_invite(cls, email, inviter_name, signup_url, format_label=None):
        """Invite-to-non-user (Phase 4 §3). Transactional — the recipient
        has no account (and no ``email_notifications`` preference), so this
        bypasses ``_notify`` like the waitlist mails do. Volume is capped by
        the create-invite rate budget upstream."""
        subject = f"{inviter_name} invited you to Paradise Sports"
        template_path = "invite/signupInvite.html"
        context = {
            'inviter_name': inviter_name,
            'signup_url': signup_url,
            'format_label': format_label,
        }
        send_email.defer(subject=subject, recipient=email,
                         template_path=template_path, context=context)

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
