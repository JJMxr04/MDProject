"""Match format presets — end-to-end behavior.

Covers: each preset's shape (games per player + shared Golden Game, window
length), the fixture-availability rejection message, format threading
through invite payloads, the pre-submit availability endpoint, and the
rematch CTA (same format, roles swapped, idempotent, instrumented).
"""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.game.models.game import FixtureUnavailable
from core.mail.models import Invite
from core.match import formats
from core.match.models import Match
from core.match.tests.factories import (
    make_golden_seed_selection,
    make_match,
    make_user,
    mock_golden_seed,
)
from core.metrics.models import ProductEvent


def patch_catalog(items):
    """Patch the aggregator listing to return exactly ``items``."""
    client = MagicMock()
    client.list_events.return_value = {"items": items}
    return patch(
        "core.event.providers.aggregator_client.AggrigatorClient",
        return_value=client,
    )


def priced_items(n, prefix="evt"):
    """``n`` distinct events, each with one priced MONEYLINE market —
    the minimal shape ``count_available_events`` counts as available."""
    return [
        {
            "id": f"{prefix}-{i}",
            "markets": [{
                "category": "MONEYLINE", "scope": "FULL_GAME",
                "selections": [{
                    "id": f"{prefix}-{i}-ml:home",
                    "type": "HOME",
                    "decimal_odds": "1.90",
                }],
            }],
        }
        for i in range(n)
    ]


class FormatPresetTests(TestCase):
    def test_each_preset_creates_right_shape(self):
        """Every preset: 2 * games_per_player regular slots + 1 shared
        Golden Game, and a window of the preset's length."""
        for fmt, cfg in formats.MATCH_FORMATS.items():
            with self.subTest(format=fmt):
                p1 = make_user(f"{fmt.lower()}_p1")
                p2 = make_user(f"{fmt.lower()}_p2")
                sel = make_golden_seed_selection()
                with mock_golden_seed(sel):
                    match = Match.objects.create_match(
                        p1, p2, match_format=fmt,
                    )
                self.assertEqual(match.format, fmt)
                self.assertEqual(match.games_per_player, cfg["games_per_player"])
                self.assertEqual(
                    match.games.count(), 2 * cfg["games_per_player"] + 1,
                )
                self.assertEqual(match.games.filter(is_golden=True).count(), 1)
                expected_end = timezone.now() + timedelta(days=cfg["days"])
                self.assertAlmostEqual(
                    match.end_date.timestamp(),
                    expected_end.timestamp(),
                    delta=60,
                )

    def test_blitz_rejected_in_empty_window_with_useful_message(self):
        p1 = make_user("blitz_p1")
        p2 = make_user("blitz_p2")
        with patch_catalog([]):
            with self.assertRaises(FixtureUnavailable) as ctx:
                Match.objects.create_match(p1, p2, match_format="BLITZ")
        message = str(ctx.exception)
        self.assertIn("Only 0 games available", message)
        self.assertIn("Blitz", message)
        self.assertEqual(Match.objects.count(), 0)


class InviteFormatThreadingTests(TestCase):
    def test_accept_invite_threads_format_into_match(self):
        p1 = make_user("inviter")
        p2 = make_user("invitee")
        sel = make_golden_seed_selection()
        with mock_golden_seed(sel):
            invite = Invite.objects.create_invite(
                obj_id=None,
                player=p2,
                invite_type="match",
                sender=p1,
                payload={"format": "BLITZ"},
            )
            Invite.objects.accept_invite(invite)

        match = Match.objects.get()
        self.assertEqual(match.format, "BLITZ")
        self.assertEqual(match.player_1, p1)
        self.assertEqual(match.player_2, p2)
        # 2 per player + 1 golden.
        self.assertEqual(match.games.count(), 5)

        # Invite rows are kept for history now — state flips, no delete.
        invite.refresh_from_db()
        self.assertEqual(invite.state, "accepted")
        self.assertTrue(invite.accepted)


class MatchAvailabilityViewTests(TestCase):
    def setUp(self):
        self.user = make_user("checker")
        self.client.force_login(self.user)
        self.url = reverse("core-portal:portal-match-availability")

    def test_blitz_viable_with_exactly_three_events(self):
        with patch_catalog(priced_items(3)):
            r = self.client.get(self.url, {"format": "BLITZ"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["format"], "BLITZ")
        self.assertEqual(body["available"], 3)
        self.assertEqual(body["needed"], 3)
        self.assertTrue(body["viable"])

    def test_classic_not_viable_with_three_events(self):
        with patch_catalog(priced_items(3)):
            r = self.client.get(self.url, {"format": "CLASSIC"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["format"], "CLASSIC")
        self.assertEqual(body["available"], 3)
        self.assertEqual(body["needed"], 4)
        self.assertFalse(body["viable"])


class RematchTests(TestCase):
    def setUp(self):
        self.p1 = make_user("rematch_p1")
        self.p2 = make_user("rematch_p2")
        self.match = make_match(self.p1, self.p2)
        self.url = reverse(
            "core-portal:portal-match-rematch", args=[self.match.id],
        )

    def _complete_match(self):
        self.match.match_state = "completed"
        self.match.winner = self.p1
        self.match.save(update_fields=["match_state", "winner"])

    def _post(self):
        return self.client.post(
            self.url, data=json.dumps({}), content_type="application/json",
        )

    def test_loser_rematch_creates_invite_and_tracks(self):
        self._complete_match()
        self.client.force_login(self.p2)
        with patch_catalog(priced_items(6)):
            r = self._post()
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "success")

        invite = Invite.objects.get(type="match")
        self.assertEqual(str(invite.id), str(body["invite_id"]))
        self.assertEqual(invite.sender, self.p2)
        self.assertEqual(invite.player, self.p1)
        self.assertEqual(invite.state, "sent")
        self.assertEqual(invite.payload["format"], self.match.format)
        self.assertEqual(invite.payload["rematch_of"], str(self.match.id))

        events = ProductEvent.objects.filter(name="rematch_clicked")
        self.assertEqual(events.count(), 1)
        event = events.get()
        self.assertEqual(event.user, self.p2)
        self.assertEqual(event.props["match_id"], str(self.match.id))
        self.assertEqual(event.props["format"], self.match.format)

    def test_second_click_returns_existing_invite(self):
        self._complete_match()
        self.client.force_login(self.p2)
        with patch_catalog(priced_items(6)):
            first = self._post()
            second = self._post()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            str(first.json()["invite_id"]), str(second.json()["invite_id"]),
        )
        self.assertEqual(
            Invite.objects.filter(
                type="match", sender=self.p2, player=self.p1,
            ).count(),
            1,
        )

    def test_rematch_on_non_completed_match_is_400(self):
        # Match is in 'accepted' state from the factory — no rematch yet.
        self.client.force_login(self.p2)
        r = self._post()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Invite.objects.filter(type="match").count(), 0)

    def test_non_participant_is_rejected(self):
        self._complete_match()
        outsider = make_user("outsider")
        self.client.force_login(outsider)
        r = self._post()
        # player_in_match_required currently returns 403 for non-players
        # (spec language says 404 — see report; either way, no invite).
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Invite.objects.filter(type="match").count(), 0)
