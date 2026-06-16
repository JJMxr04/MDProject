import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from core.event.admin import TeamAdminForm


def _img_upload(name, fmt, content_type):
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (5, 6, 7)).save(buf, format=fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)


class TeamAdminFormLogoTests(SimpleTestCase):
    """The admin logo upload routes through the shared image-security pipeline.

    We validate ``clean_logo_url`` in isolation: the form is intentionally
    missing other required Team fields (so ``is_valid()`` is False overall), but
    per-field cleaning still runs, which is all these tests inspect.
    """

    def test_valid_logo_is_reencoded_to_webp(self):
        form = TeamAdminForm(data={}, files={"logo_url": _img_upload("logo.png", "PNG", "image/png")})
        form.is_valid()
        cleaned = form.cleaned_data.get("logo_url")
        self.assertIsNotNone(cleaned)
        self.assertTrue(cleaned.name.endswith(".webp"))

    def test_svg_logo_rejected(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        form = TeamAdminForm(
            data={}, files={"logo_url": SimpleUploadedFile("x.svg", svg, "image/svg+xml")}
        )
        form.is_valid()
        self.assertIn("logo_url", form.errors)

    def test_disallowed_raster_format_rejected(self):
        # BMP opens fine in Pillow but is not in our ALLOWED_INPUT_FORMATS, so it
        # must be rejected by validate_image_file (not by Django's ImageField).
        form = TeamAdminForm(
            data={}, files={"logo_url": _img_upload("x.bmp", "BMP", "image/bmp")}
        )
        form.is_valid()
        self.assertIn("logo_url", form.errors)

    def test_missing_logo_is_not_an_error(self):
        # No file uploaded → logo_url cleans to an empty value, no logo error.
        form = TeamAdminForm(data={}, files={})
        form.is_valid()
        self.assertNotIn("logo_url", form.errors)
