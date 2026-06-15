"""``build_available_events`` windowing for the pick popup.

Events must start late enough to clear the owner deadline yet early enough to
finish + settle before ``match.end_date``. The aggregator gives only a
``start_time`` (no end/duration), so "fits inside the match timeframe" is
approximated as ``start_time + EVENT_COMPLETION_BUFFER <= match.end_date`` —
which matters most on the short Blitz (2-day) window.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from core.match.tests.factories import make_match, make_user
from core.match.views import available_events as ae


def _catalog(items=None):
    client = MagicMock()
    client.list_events.return_value = {"items": items or []}
    # Patch the name as bound inside available_events (imported at module top),
    # not the source module — otherwise the real client is used.
    return patch.object(ae, "AggrigatorClient", return_value=client), client


class BuildAvailableEventsWindowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.u1 = make_user("a")
        self.u2 = make_user("b")

    def _match(self, *, days):
        return make_match(
            self.u1, self.u2, end_date=timezone.now() + timedelta(days=days),
        )

    def test_upper_bound_pulls_in_completion_buffer(self):
        match = self._match(days=2)  # Blitz-length window
        p, client = _catalog([])
        with p:
            ae.build_available_events(match)
        kwargs = client.list_events.call_args.kwargs
        got = datetime.fromisoformat(kwargs["starts_before"])
        expected = match.end_date - ae.EVENT_COMPLETION_BUFFER
        self.assertAlmostEqual(got, expected, delta=timedelta(seconds=1))
        # Lower bound is still the owner-deadline buffer off now.
        starts_after = datetime.fromisoformat(kwargs["starts_after"])
        self.assertGreater(starts_after, timezone.now())

    def test_closed_window_returns_empty_without_hitting_aggregator(self):
        # match.end_date so close that (end_date - completion buffer) is already
        # earlier than the owner-deadline lower bound → no event can qualify.
        match = self._match(days=7)
        match.end_date = timezone.now() + timedelta(hours=2)
        match.save(update_fields=["end_date"])
        cache.clear()
        p, client = _catalog([{"id": "evt-1", "markets": []}])
        with p:
            out = ae.build_available_events(match)
        self.assertEqual(out, [])
        client.list_events.assert_not_called()
