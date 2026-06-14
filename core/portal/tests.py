from django.test import RequestFactory, TestCase

from core.portal.templatetags.portal_nav import sidenav_item


class SidenavItemActiveStateTests(TestCase):
    """The sidebar marks exactly one item active per page. The Matches item's
    prefix (``/web/portal/match/``) is the parent of the Duel subtree
    (``/web/portal/match/duels/``); ``exclude`` keeps both from highlighting
    on the duels page (regression for the double-selected sidebar)."""

    def setUp(self):
        self.factory = RequestFactory()

    def _ctx(self, path):
        return {"request": self.factory.get(path)}

    def _matches(self, path):
        return sidenav_item(
            self._ctx(path),
            url="core-portal:portal-my-match-list",
            icon="controller", label="Matches",
            prefix="/web/portal/match/",
            exclude="/web/portal/match/duels/",
        )["is_active"]

    def _duel(self, path):
        return sidenav_item(
            self._ctx(path),
            url="core-portal:portal-duels",
            icon="fire", label="Duel",
            prefix="/web/portal/match/duels/",
        )["is_active"]

    def test_duels_page_activates_only_duel(self):
        path = "/web/portal/match/duels/"
        self.assertFalse(self._matches(path))
        self.assertTrue(self._duel(path))

    def test_match_page_activates_only_matches(self):
        path = "/web/portal/match/12345/"
        self.assertTrue(self._matches(path))
        self.assertFalse(self._duel(path))

    def _friends(self, path):
        return sidenav_item(
            self._ctx(path),
            url="core-portal:friend_search",
            icon="people", label="Friends",
            prefix="/web/portal/user/",
            exclude="/web/portal/user/profile/",
        )["is_active"]

    def _settings(self, path):
        return sidenav_item(
            self._ctx(path),
            url="core-portal:profile",
            icon="gear", label="Settings",
            prefix="/web/portal/user/profile/,/web/portal/billing/",
        )["is_active"]

    def test_profile_page_activates_only_settings(self):
        # Settings (/web/portal/user/profile/) is nested under the Friends
        # prefix (/web/portal/user/); only Settings should highlight here.
        path = "/web/portal/user/profile/"
        self.assertFalse(self._friends(path))
        self.assertTrue(self._settings(path))

    def test_friends_page_activates_only_friends(self):
        path = "/web/portal/user/friends/search/"
        self.assertTrue(self._friends(path))
        self.assertFalse(self._settings(path))

    def test_exclude_accepts_comma_list(self):
        ctx = self._ctx("/web/portal/match/duels/")
        active = sidenav_item(
            ctx, url="core-portal:portal-my-match-list",
            icon="controller", label="Matches",
            prefix="/web/portal/match/",
            exclude="/web/portal/match/duels/,/web/portal/match/other/",
        )["is_active"]
        self.assertFalse(active)
