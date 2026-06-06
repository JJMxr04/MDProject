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
