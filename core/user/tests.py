from django.test import TestCase
from django.urls import reverse

from core.match.tests.factories import make_user


class UserAdminPasswordTests(TestCase):
    """The user change form shows a reset link, never the password hash."""

    def setUp(self):
        self.staff = make_user("admin")
        self.staff.is_staff = True
        self.staff.is_superuser = True
        self.staff.save(update_fields=["is_staff", "is_superuser"])
        self.client.force_login(self.staff)
        self.target = make_user("target")

    def test_change_form_has_reset_link_but_no_hash_field(self):
        response = self.client.get(
            reverse("admin:core_user_user_change", args=[self.target.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset password")
        password_url = reverse(
            "admin:auth_user_password_change", args=[self.target.pk]
        )
        self.assertContains(response, password_url)
        # The ReadOnlyPasswordHashField widget is gone — no algorithm/hash
        # summary anywhere on the page.
        self.assertNotContains(response, "algorithm")
        self.assertNotContains(response, 'name="password"')

    def test_password_change_form_still_works(self):
        url = reverse("admin:auth_user_password_change", args=[self.target.pk])
        self.assertEqual(self.client.get(url).status_code, 200)

        response = self.client.post(url, {
            "password1": "n3w-Sup3r-secret!",
            "password2": "n3w-Sup3r-secret!",
        })
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password("n3w-Sup3r-secret!"))
