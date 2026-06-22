"""Render tests for the shared Pick-of-the-Day hype partial across its states."""
from __future__ import annotations

from datetime import timedelta

from django.template import Context, Template
from django.test import TestCase

from core.match.tests.factories import make_user
from core.potd.models import DailyPick, DailyPickResult

# Reuse the POTD factory from the main suite.
from core.potd.tests.test_potd import make_potd
from core.potd.views import potd_card_context

TPL = Template('{% include "portal/potd/_potd_hype.html" %}')


def _render(user):
    return TPL.render(Context(potd_card_context(user)))


class PotdHypePartialTests(TestCase):
    def test_open_state_shows_countdown_and_pick_buttons(self):
        make_potd()
        html = _render(make_user("v"))
        self.assertIn("data-countdown-to", html)
        self.assertIn('data-action="potd-pick"', html)
        # The "pick now" state stays focused on the CTA — no next-pick timer.
        self.assertNotIn("potd-hype__countdown--next", html)

    def test_crowd_bar_hidden_below_threshold(self):
        potd, home, away = make_potd()
        DailyPick.objects.create(user=make_user("h"), potd=potd, selection=home)
        html = _render(make_user("v"))
        self.assertNotIn("potd-hype__crowd-bar", html)
        self.assertIn("in so far", html)   # cold-start copy

    def test_crowd_bar_shown_above_threshold(self):
        potd, home, away = make_potd()
        for i in range(12):
            DailyPick.objects.create(user=make_user(f"h{i}"), potd=potd, selection=home)
        html = _render(make_user("v"))
        self.assertIn("potd-hype__crowd-bar", html)

    def test_locked_in_state_no_buttons(self):
        potd, home, away = make_potd()
        v = make_user("v")
        DailyPick.objects.record_pick(user=v, potd=potd, selection=home)
        html = _render(v)
        self.assertIn("LOCKED IN", html)
        self.assertNotIn('data-action="potd-pick"', html)
        # Pending pick → also count down to the next pick.
        self.assertIn("potd-hype__countdown--next", html)

    def test_won_result_state(self):
        potd, home, away = make_potd()
        v = make_user("v")
        DailyPick.objects.create(
            user=v, potd=potd, selection=home, result=DailyPickResult.WON)
        html = _render(v)
        self.assertIn("YOU WON", html)
        self.assertNotIn('data-action="potd-pick"', html)
        # Settled pick → count down to the next pick.
        self.assertIn("potd-hype__countdown--next", html)

    def test_missed_state_when_locked_without_pick(self):
        make_potd(lock_in=timedelta(hours=-1))   # already kicked off
        html = _render(make_user("v"))
        self.assertNotIn('data-action="potd-pick"', html)
        self.assertIn("back tomorrow", html.lower())
        # Closed/missed → count down to the next pick.
        self.assertIn("potd-hype__countdown--next", html)

    def test_no_potd_shows_empty_card_with_next_countdown(self):
        # No pick curated today → empty-state card with the next-pick timer
        # and no pickable selections.
        html = _render(make_user("v"))
        self.assertIn("potd-hype--empty", html)
        self.assertIn("potd-hype__countdown--next", html)
        self.assertNotIn('data-action="potd-pick"', html)
