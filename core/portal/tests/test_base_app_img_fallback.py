"""base_app.html must load the CSP-safe broken-image fallback script."""
from django.template import Context, Template
from django.test import SimpleTestCase


class BaseAppImgFallbackTests(SimpleTestCase):
    def test_base_app_includes_img_fallback_script(self):
        # Render a child that extends base_app with empty blocks; the
        # <script> tags in base_app render regardless of auth state.
        tpl = Template('{% extends "portal/base_app.html" %}')
        html = tpl.render(Context({}))
        self.assertIn("js/portal/img-fallback.js", html)
