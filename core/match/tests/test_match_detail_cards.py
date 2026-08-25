"""Match-detail game cards — market labels.

Regular slots surface the market the owner's pick established; the golden
card's locked-market label is covered in ``test_tiebreaker_window``.
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.event.models import MarketCategory
from core.game.models import Game
from core.match.tests.factories import (
    make_event,
    make_league,
    make_market,
    make_match,
    make_selection,
    make_user,
)


class MatchHeaderLevelFlairTests(TestCase):
    """Players carry a level chip on the match-detail header."""

    def test_header_shows_opponent_level_chip(self):
        from core.ranking.models import PlayerProgress

        p1 = make_user("p1")
        p2 = make_user("p2")
        PlayerProgress.objects.filter(user=p2).update(level=9)  # row exists from signup
        match = make_match(p1, p2)

        self.client.force_login(p1)
        url = reverse("core-portal:portal-my-match-detail", args=[match.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Lv 9")

    def test_header_omits_chip_for_unranked_player(self):
        from core.ranking.models import PlayerProgress

        p1 = make_user("p1")
        p2 = make_user("p2")
        match = make_match(p1, p2)
        # Defensive path: no progress rows → no chip (level falsy). Every user
        # normally has a row from signup, so delete to simulate the gap.
        PlayerProgress.objects.filter(user__in=[p1, p2]).delete()

        self.client.force_login(p1)
        url = reverse("core-portal:portal-my-match-detail", args=[match.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "lvl-chip")

    def test_header_shows_division_chip_from_active_season(self):
        from datetime import date

        from core.ranking.models import Season, SeasonParticipation

        p1 = make_user("p1")
        p2 = make_user("p2")
        season = Season.objects.create(
            name="Q1", status=Season.Status.ACTIVE,
            start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
        )
        SeasonParticipation.objects.create(user=p2, season=season, division=3)
        match = make_match(p1, p2)

        self.client.force_login(p1)
        url = reverse("core-portal:portal-my-match-detail", args=[match.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Div 3")


class RegularCardMarketTests(TestCase):
    def test_regular_card_shows_picked_market(self):
        p1 = make_user("p1")
        p2 = make_user("p2")
        match = make_match(p1, p2)
        league = make_league()
        event = make_event(league, start_time=timezone.now() + timedelta(days=2))
        total = make_market(event, category=MarketCategory.TOTAL, line=44.5)
        over = make_selection(total, selection_type="OVER")
        Game.objects.upload_pick(
            current_user=p1, match=match,
            event_id=event.id, selection_id=over.id,
        )

        self.client.force_login(p1)
        url = reverse("core-portal:portal-my-match-detail", args=[match.id])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Market: Total @ +44.5")
