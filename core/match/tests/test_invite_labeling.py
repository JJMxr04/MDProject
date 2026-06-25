"""Match-type labeling in invite + acceptance emails.

Duels, format matches, and plain matches must read distinctly in the subject
line (which is also the in-app notification text) — not all collapse to the
word "match".
"""
from __future__ import annotations

from django.test import TestCase, override_settings
from procrastinate.contrib.django.models import ProcrastinateJob

from core.mail.models import Emails
from core.match.tests.factories import make_user


def _subject_to(email):
    job = (
        ProcrastinateJob.objects.filter(
            task_name="core.mail.send_email", args__recipient=email,
        )
        .order_by("id")
        .last()
    )
    return job.args["subject"]


@override_settings(USE_AGGRIGATOR=False)
class InviteEmailLabelingTests(TestCase):
    def test_match_invite_subject_includes_format_and_sender(self):
        user = make_user("lbl_r")
        Emails.send_match_invite(user, "alex", format_label="Blitz")
        subject = _subject_to(user.email)
        self.assertIn("Blitz", subject)
        self.assertIn("alex", subject)

    def test_match_invite_subject_without_format_still_reads_as_match(self):
        user = make_user("lbl_r2")
        Emails.send_match_invite(user, "alex")
        subject = _subject_to(user.email)
        self.assertIn("alex", subject)
        self.assertIn("match", subject.lower())

    def test_acceptance_confirmation_labels_duel(self):
        sender = make_user("lbl_s1")
        Emails.send_match_acceptance_confirmation(sender, "bob", kind_label="duel")
        self.assertIn("duel", _subject_to(sender.email).lower())

    def test_acceptance_confirmation_labels_format_match(self):
        sender = make_user("lbl_s2")
        Emails.send_match_acceptance_confirmation(
            sender, "bob", kind_label="BLITZ match",
        )
        self.assertIn("BLITZ match", _subject_to(sender.email))

    def test_started_to_accepter_labels_duel(self):
        user = make_user("lbl_a1")
        Emails.send_match_started_to_accepter(user, "carol", kind_label="duel")
        self.assertIn("duel", _subject_to(user.email).lower())

    def test_started_to_accepter_labels_format_match(self):
        user = make_user("lbl_a2")
        Emails.send_match_started_to_accepter(
            user, "carol", kind_label="MARATHON match",
        )
        self.assertIn("MARATHON match", _subject_to(user.email))
