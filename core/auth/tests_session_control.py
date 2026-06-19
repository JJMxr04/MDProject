from __future__ import annotations

from datetime import timedelta

from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.auth.models import LoginEvent
from core.auth.services.login_security import (
    active_sessions_for_user,
    recent_activity_for_user,
    revoke_all_sessions,
    revoke_other_sessions,
    revoke_session,
)
from core.user.models import User


def _make_session(key):
    return Session.objects.create(
        session_key=key, session_data="x",
        expire_date=timezone.now() + timedelta(days=1),
    )


def _auth_session(user):
    """A real authenticated DB session for ``user``; returns its session_key."""
    store = SessionStore()
    store["_auth_user_id"] = str(user.pk)
    store.create()
    return store.session_key


@override_settings(USE_AGGRIGATOR=False)
class SessionRevocationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="rev", email="rev@test.local", password="pw",
        )
        for k in ("keep", "drop1", "drop2"):
            _make_session(k)
            LoginEvent.objects.create(
                user=self.user, event_type=LoginEvent.SUCCESS, session_key=k,
            )

    def test_revoke_others_keeps_current(self):
        n = revoke_other_sessions(self.user, keep_session_key="keep")
        self.assertEqual(n, 2)
        self.assertTrue(Session.objects.filter(session_key="keep").exists())
        self.assertFalse(Session.objects.filter(session_key="drop1").exists())

    def test_revoke_all(self):
        n = revoke_all_sessions(self.user)
        self.assertEqual(n, 3)
        self.assertFalse(Session.objects.filter(session_key__in=["keep", "drop1", "drop2"]).exists())


@override_settings(USE_AGGRIGATOR=False)
class SessionControlViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="vic", email="vic@test.local", password="pw",
        )
        self.client.force_login(self.user)

    def test_logout_others_is_post_only(self):
        resp = self.client.get(reverse("core-auth:logout-others"))
        self.assertEqual(resp.status_code, 405)

    def test_logout_others_revokes_and_redirects(self):
        for k in ("foreignA", "foreignB"):
            _make_session(k)
            LoginEvent.objects.create(
                user=self.user, event_type=LoginEvent.SUCCESS, session_key=k,
            )
        resp = self.client.post(reverse("core-auth:logout-others"))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Session.objects.filter(session_key="foreignA").exists())

    def test_not_me_logs_out_and_redirects_to_password_reset(self):
        resp = self.client.post(reverse("core-auth:security-not-me"))
        self.assertEqual(resp.status_code, 302)
        # Session flushed → user no longer authenticated.
        self.assertNotIn("_auth_user_id", self.client.session)


@override_settings(USE_AGGRIGATOR=False)
class SecurityPageActionsRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="wes", email="wes@test.local", password="pw",
        )
        self.client.force_login(self.user)

    def test_action_forms_render(self):
        resp = self.client.get(reverse("core-auth:2fa-security"))
        self.assertContains(resp, reverse("core-auth:logout-others"))
        self.assertContains(resp, reverse("core-auth:security-not-me"))


@override_settings(USE_AGGRIGATOR=False)
class SecurityTabsRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tab", email="tab@test.local", password="pw",
        )
        self.client.force_login(self.user)

    def test_three_tabs_render(self):
        resp = self.client.get(reverse("core-auth:2fa-security"))
        self.assertContains(resp, "Two-factor")
        self.assertContains(resp, "Active sessions")
        self.assertContains(resp, "Recent activity")

    def test_active_session_listed_with_revoke_form(self):
        key = _auth_session(self.user)
        LoginEvent.objects.create(
            user=self.user, event_type=LoginEvent.SUCCESS, session_key=key,
            device_label="Firefox on Windows",
        )
        resp = self.client.get(reverse("core-auth:2fa-security"))
        self.assertContains(resp, "Firefox on Windows")
        self.assertContains(resp, reverse("core-auth:revoke-session"))

    def test_tab_query_param_selects_sessions_tab(self):
        resp = self.client.get(reverse("core-auth:2fa-security") + "?tab=sessions")
        # seg-b (sessions) carries the checked attribute when ?tab=sessions.
        self.assertContains(resp, 'id="seg-b" checked')

    def test_tab_switching_css_is_loaded(self):
        # The seg-tabs CSS must ship with the page or the radios do nothing
        # (panes stack, labels don't switch). Guards the missing-cards.css bug.
        resp = self.client.get(reverse("core-auth:2fa-security"))
        self.assertContains(resp, "#seg-b:checked ~ #pane-b")
        self.assertContains(resp, ".seg-pane { display: none; }")


@override_settings(USE_AGGRIGATOR=False)
class ConfirmFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="cf", email="cf@test.local", password="pw",
        )
        self.other = User.objects.create_user(
            username="cfo", email="cfo@test.local", password="pw",
        )
        self.client.force_login(self.user)

    def test_not_me_confirm_renders_execute_form(self):
        resp = self.client.get(reverse("core-auth:security-not-me-confirm"))
        self.assertEqual(resp.status_code, 200)
        # Interstitial posts to the real executor, doesn't act itself.
        self.assertContains(resp, reverse("core-auth:security-not-me"))

    def test_revoke_confirm_is_post_only(self):
        resp = self.client.get(reverse("core-auth:revoke-session-confirm"))
        self.assertEqual(resp.status_code, 405)

    def test_revoke_confirm_shows_device_and_execute_form(self):
        key = _auth_session(self.user)
        LoginEvent.objects.create(
            user=self.user, event_type=LoginEvent.SUCCESS, session_key=key,
            device_label="Edge on Windows",
        )
        resp = self.client.post(
            reverse("core-auth:revoke-session-confirm"), {"session_key": key},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Edge on Windows")
        self.assertContains(resp, reverse("core-auth:revoke-session"))
        # The session is NOT signed out merely by viewing the confirmation.
        self.assertTrue(Session.objects.filter(session_key=key).exists())

    def test_revoke_confirm_unknown_session_redirects(self):
        resp = self.client.post(
            reverse("core-auth:revoke-session-confirm"), {"session_key": "nope"},
        )
        self.assertEqual(resp.status_code, 302)

    def test_revoke_confirm_rejects_foreign_session(self):
        key = _auth_session(self.other)
        LoginEvent.objects.create(
            user=self.other, event_type=LoginEvent.SUCCESS, session_key=key,
        )
        resp = self.client.post(
            reverse("core-auth:revoke-session-confirm"), {"session_key": key},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Session.objects.filter(session_key=key).exists())


@override_settings(USE_AGGRIGATOR=False)
class ActiveSessionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="act", email="act@test.local", password="pw",
        )
        self.other = User.objects.create_user(
            username="oth", email="oth@test.local", password="pw",
        )

    def _login_event(self, user, key, **kw):
        return LoginEvent.objects.create(
            user=user, event_type=LoginEvent.SUCCESS, session_key=key, **kw,
        )

    def test_lists_only_live_sessions_for_this_user(self):
        live = _auth_session(self.user)
        self._login_event(self.user, live, device_label="Chrome on macOS", country="US")

        expired = _auth_session(self.user)
        self._login_event(self.user, expired)
        Session.objects.filter(session_key=expired).update(
            expire_date=timezone.now() - timedelta(days=1)
        )

        foreign = _auth_session(self.other)
        self._login_event(self.other, foreign)

        rows = active_sessions_for_user(self.user, current_session_key=live)
        keys = [r["session_key"] for r in rows]
        self.assertEqual(keys, [live])
        self.assertNotIn(expired, keys)
        self.assertNotIn(foreign, keys)
        self.assertTrue(rows[0]["is_current"])
        self.assertEqual(rows[0]["device_label"], "Chrome on macOS")

    def test_revoke_session_owned(self):
        key = _auth_session(self.user)
        self._login_event(self.user, key)
        self.assertTrue(revoke_session(self.user, key))
        self.assertFalse(Session.objects.filter(session_key=key).exists())

    def test_cannot_revoke_another_users_session(self):
        key = _auth_session(self.other)
        self._login_event(self.other, key)
        self.assertFalse(revoke_session(self.user, key))
        self.assertTrue(Session.objects.filter(session_key=key).exists())

    def test_recent_activity_excludes_logout(self):
        LoginEvent.objects.create(user=self.user, event_type=LoginEvent.SUCCESS)
        LoginEvent.objects.create(user=self.user, event_type=LoginEvent.FAILED)
        LoginEvent.objects.create(user=self.user, event_type=LoginEvent.LOGOUT)
        types = {a.event_type for a in recent_activity_for_user(self.user)}
        self.assertIn(LoginEvent.SUCCESS, types)
        self.assertIn(LoginEvent.FAILED, types)
        self.assertNotIn(LoginEvent.LOGOUT, types)


@override_settings(USE_AGGRIGATOR=False)
class RevokeSessionViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="rsv", email="rsv@test.local", password="pw",
        )
        self.other = User.objects.create_user(
            username="rso", email="rso@test.local", password="pw",
        )
        self.client.force_login(self.user)

    def test_revoke_session_is_post_only(self):
        resp = self.client.get(reverse("core-auth:revoke-session"))
        self.assertEqual(resp.status_code, 405)

    def test_revokes_own_session_and_redirects(self):
        key = _auth_session(self.user)
        LoginEvent.objects.create(
            user=self.user, event_type=LoginEvent.SUCCESS, session_key=key,
        )
        resp = self.client.post(reverse("core-auth:revoke-session"), {"session_key": key})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Session.objects.filter(session_key=key).exists())

    def test_cannot_revoke_foreign_session(self):
        key = _auth_session(self.other)
        LoginEvent.objects.create(
            user=self.other, event_type=LoginEvent.SUCCESS, session_key=key,
        )
        resp = self.client.post(reverse("core-auth:revoke-session"), {"session_key": key})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Session.objects.filter(session_key=key).exists())
