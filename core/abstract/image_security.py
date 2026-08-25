"""Single source of truth for hardening every image upload.

Validate real bytes → cap size/pixels → re-encode to WEBP (drops polyglots,
EXIF/GPS, ICC, comments) → callers store under a random UUID key.
"""

from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps
from rest_framework import serializers

ALLOWED_INPUT_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
OUTPUT_FORMAT = "WEBP"
OUTPUT_EXTENSION = "webp"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_MEGAPIXELS = 24
MAX_DIMENSION = 1024

# Make Pillow itself refuse decompression bombs at our threshold.
Image.MAX_IMAGE_PIXELS = MAX_MEGAPIXELS * 1_000_000


def validate_image_file(file):
    """Raise ValidationError unless ``file`` is a safe, in-bounds raster image."""
    size = getattr(file, "size", None)
    if size is not None and size > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"Image is too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )

    file.seek(0)
    try:
        probe = Image.open(file)
        probe.verify()  # consumes the file object; must reopen below
    except Exception:
        raise ValidationError("File is not a valid image.")

    file.seek(0)
    img = Image.open(file)
    if img.format not in ALLOWED_INPUT_FORMATS:
        raise ValidationError(
            f"Unsupported image type '{img.format}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_INPUT_FORMATS))}."
        )

    width, height = img.size
    if width * height > MAX_MEGAPIXELS * 1_000_000:
        raise ValidationError("Image dimensions are too large.")

    file.seek(0)


def process_image(file):
    """Decode and re-encode ``file`` to a sanitized WEBP ``ContentFile``.

    Re-encoding from decoded pixels drops appended payloads, EXIF/GPS, ICC,
    and comment segments, and downscales to MAX_DIMENSION. Orientation is
    baked in via ``exif_transpose`` before metadata is lost.
    """
    file.seek(0)
    img = Image.open(file)
    img = ImageOps.exif_transpose(img)

    if img.mode in ("P", "LA", "RGBA"):
        img = img.convert("RGBA")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))  # downscale only

    buf = BytesIO()
    img.save(buf, format=OUTPUT_FORMAT, quality=85, method=6)
    return ContentFile(buf.getvalue(), name=f"image.{OUTPUT_EXTENSION}")


class SecureImageField(serializers.ImageField):
    """DRF image field that validates and re-encodes on input.

    ``to_internal_value`` returns a sanitized WEBP ``ContentFile`` ready to hand
    to ``ImageField.save``; the original bytes never reach storage.
    """

    def to_internal_value(self, data):
        file = super().to_internal_value(data)  # DRF: basic image open
        validate_image_file(file)
        return process_image(file)
