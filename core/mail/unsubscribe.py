"""Signed unsubscribe tokens for engagement emails.

The token carries the user's ``public_id`` signed with SECRET_KEY — the link
works logged-out, can't be forged, and doesn't expose a guessable id. No
expiry: an unsubscribe link in an old email must keep working (CAN-SPAM
expects 30+ days; forever is simpler and safer).
"""

from django.conf import settings
from django.core import signing

SALT = "core.mail.unsubscribe"


def make_token(user) -> str:
    return signing.dumps({"uid": str(user.public_id)}, salt=SALT)


def unsubscribe_url(user) -> str:
    from django.urls import reverse

    return settings.SITE_URL + reverse("core-auth:unsubscribe", args=[make_token(user)])


def read_token(token: str):
    """Return the user public_id the token was minted for, or None."""
    try:
        return signing.loads(token, salt=SALT)["uid"]
    except (signing.BadSignature, KeyError, TypeError):
        return None
