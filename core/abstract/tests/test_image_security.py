import io

from django.conf import settings as dj_settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from PIL import Image

from core.abstract import image_security as imgsec


def _png_bytes(size=(64, 64), color=(10, 20, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(name, data, content_type="image/png"):
    return SimpleUploadedFile(name, data, content_type=content_type)


class ValidateImageFileTests(SimpleTestCase):
    def test_accepts_a_real_png(self):
        imgsec.validate_image_file(_upload("a.png", _png_bytes()))

    def test_rejects_oversized_file(self):
        big = _png_bytes() + b"\x00" * (imgsec.MAX_UPLOAD_BYTES + 1)
        with self.assertRaises(ValidationError):
            imgsec.validate_image_file(_upload("big.png", big))

    def test_rejects_non_image_bytes(self):
        with self.assertRaises(ValidationError):
            imgsec.validate_image_file(_upload("x.png", b"not an image"))

    def test_rejects_svg(self):
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        with self.assertRaises(ValidationError):
            imgsec.validate_image_file(_upload("x.svg", svg, "image/svg+xml"))

    def test_rejects_oversized_dimensions(self):
        # Header claims a huge canvas → over the megapixel cap.
        side = int((imgsec.MAX_MEGAPIXELS * 1_000_000) ** 0.5) + 50
        bomb = _png_bytes(size=(side, side))
        with self.assertRaises(ValidationError):
            imgsec.validate_image_file(_upload("bomb.png", bomb))

    def test_seeks_file_back_to_zero(self):
        f = _upload("a.png", _png_bytes())
        imgsec.validate_image_file(f)
        self.assertEqual(f.tell(), 0)


class ProcessImageTests(SimpleTestCase):
    def test_output_is_webp(self):
        out = imgsec.process_image(_upload("a.png", _png_bytes()))
        reopened = Image.open(io.BytesIO(out.read()))
        self.assertEqual(reopened.format, "WEBP")

    def test_downscales_to_max_dimension(self):
        big = _png_bytes(size=(2000, 1000))
        out = imgsec.process_image(_upload("a.png", big))
        reopened = Image.open(io.BytesIO(out.read()))
        self.assertLessEqual(max(reopened.size), imgsec.MAX_DIMENSION)

    def test_strips_trailing_payload(self):
        # A valid PNG with an appended payload (polyglot). Re-encoding from
        # pixels must drop the payload entirely.
        payload = b"<?php system($_GET['c']); ?>"
        poly = _png_bytes() + payload
        out = imgsec.process_image(_upload("poly.png", poly))
        self.assertNotIn(payload, out.read())

    def test_strips_exif(self):
        # Build a JPEG carrying an EXIF UserComment, confirm it's gone.
        buf = io.BytesIO()
        exif = Image.Exif()
        exif[0x9286] = "secret-gps-or-comment"
        Image.new("RGB", (64, 64)).save(buf, format="JPEG", exif=exif)
        out = imgsec.process_image(_upload("e.jpg", buf.getvalue(), "image/jpeg"))
        reopened = Image.open(io.BytesIO(out.read()))
        self.assertEqual(dict(reopened.getexif()), {})

    def test_preserves_alpha(self):
        buf = io.BytesIO()
        Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(buf, format="PNG")
        out = imgsec.process_image(_upload("t.png", buf.getvalue()))
        reopened = Image.open(io.BytesIO(out.read()))
        self.assertIn(reopened.mode, ("RGBA", "LA", "P"))


class UploadSettingsTests(TestCase):
    def test_data_upload_cap_present_and_small(self):
        self.assertLessEqual(dj_settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 5 * 1024 * 1024)

    def test_file_upload_cap_present_and_small(self):
        self.assertLessEqual(dj_settings.FILE_UPLOAD_MAX_MEMORY_SIZE, 5 * 1024 * 1024)


class SecureImageFieldTests(SimpleTestCase):
    def test_returns_reencoded_webp_contentfile(self):
        field = imgsec.SecureImageField()
        out = field.to_internal_value(_upload("a.png", _png_bytes()))
        self.assertEqual(Image.open(io.BytesIO(out.read())).format, "WEBP")

    def test_rejects_bad_image(self):
        from rest_framework.exceptions import ValidationError as DRFValidationError

        field = imgsec.SecureImageField()
        with self.assertRaises((DRFValidationError, ValidationError)):
            field.to_internal_value(_upload("x.png", b"nope"))


class OutputExtensionTests(SimpleTestCase):
    def test_canonical_extension_is_webp(self):
        # The storage key extension and the transcoder output must agree so the
        # S3 object's guessed Content-Type is image/webp (non-renderable markup).
        self.assertEqual(imgsec.OUTPUT_EXTENSION, "webp")
        out = imgsec.process_image(_upload("a.png", _png_bytes()))
        self.assertTrue(out.name.endswith(".webp"))
