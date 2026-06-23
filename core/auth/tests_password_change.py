from __future__ import annotations

from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse

from core.user.models import User


@override_settings(USE_AGGRIGATOR=False)
class PasswordChangedEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pwmail", email="pwmail@test.local", password="OldPass!234",
        )

    def test_password_changed_event_defers_email_with_headline(self):
        from core.auth import twofa

        with patch("core.mail.tasks.send_email") as send_email:
            twofa.send_security_email(self.user, "password_changed")

        self.assertTrue(send_email.defer.called)
        kwargs = send_email.defer.call_args.kwargs
        self.assertEqual(kwargs["recipient"], "pwmail@test.local")
        self.assertIn("Your password was changed", kwargs["subject"])
        self.assertEqual(kwargs["context"]["headline"], "Your password was changed")
        self.assertEqual(kwargs["context"]["event"], "password_changed")


@override_settings(USE_AGGRIGATOR=False)
class SecurityPagePasswordContextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pwctx", email="pwctx@test.local", password="OldPass!234",
        )
        self.client.force_login(self.user)

    def test_security_page_exposes_password_form(self):
        resp = self.client.get(reverse("core-auth:2fa-security"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("password_form", resp.context)
        # PasswordChangeForm fields.
        self.assertIn("old_password", resp.context["password_form"].fields)
        self.assertIn("new_password1", resp.context["password_form"].fields)
        self.assertIn("new_password2", resp.context["password_form"].fields)

    def test_password_tab_query_param_selected(self):
        resp = self.client.get(reverse("core-auth:2fa-security") + "?tab=password")
        self.assertEqual(resp.context["active_tab"], "password")


@override_settings(USE_AGGRIGATOR=False)
class ChangePasswordViewTests(TestCase):
    URL_NAME = "core-auth:change-password"

    def setUp(self):
        self.user = User.objects.create_user(
            username="pwchg", email="pwchg@test.local", password="OldPass!234",
        )
        self.client.force_login(self.user)

    def _post(self, old, new):
        return self.client.post(
            reverse(self.URL_NAME),
            {"old_password": old, "new_password1": new, "new_password2": new},
        )

    def test_get_redirects_to_password_tab(self):
        resp = self.client.get(reverse(self.URL_NAME))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("tab=password", resp["Location"])

    def test_successful_change_updates_password_and_keeps_session(self):
        with patch("core.auth.views.password_change.send_security_email") as mail:
            resp = self._post("OldPass!234", "BrandNew!987")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("tab=password", resp["Location"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNew!987"))
        # Current session survives the change.
        self.assertIn("_auth_user_id", self.client.session)
        # Confirmation email queued.
        mail.assert_called_once_with(self.user, "password_changed")
        msgs = [m.message for m in get_messages(resp.wsgi_request)]
        self.assertTrue(any("password" in m.lower() for m in msgs))

    def test_wrong_current_password_rejected(self):
        with patch("core.auth.views.password_change.send_security_email") as mail:
            resp = self._post("WrongOld!000", "BrandNew!987")
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPass!234"))
        mail.assert_not_called()
        self.assertFalse(resp.context["password_form"].is_valid())

    def test_weak_new_password_rejected_by_validators(self):
        with patch("core.auth.views.password_change.send_security_email") as mail:
            resp = self._post("OldPass!234", "123")
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldPass!234"))
        mail.assert_not_called()

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.post(reverse(self.URL_NAME), {})
        self.assertEqual(resp.status_code, 302)
        # login_required bounces anonymous callers to the login URL.
        self.assertIn("login", resp["Location"].lower())


@override_settings(USE_AGGRIGATOR=False)
class SecurityPagePasswordTabRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pwtab", email="pwtab@test.local", password="OldPass!234",
        )
        self.client.force_login(self.user)

    def test_password_tab_and_form_render(self):
        resp = self.client.get(reverse("core-auth:2fa-security"))
        self.assertContains(resp, reverse("core-auth:change-password"))
        self.assertContains(resp, 'id="seg-d"')
        self.assertContains(resp, 'id="pane-d"')
        self.assertContains(resp, 'name="old_password"')
        self.assertContains(resp, 'name="new_password1"')
        self.assertContains(resp, 'name="new_password2"')

    def test_failed_change_shows_inline_error(self):
        resp = self.client.post(
            reverse("core-auth:change-password"),
            {"old_password": "WrongOld!000", "new_password1": "BrandNew!987",
             "new_password2": "BrandNew!987"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "field-error")
        self.assertEqual(resp.context["active_tab"], "password")
