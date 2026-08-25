"""HMAC signer for the Paradise channel (MDProject → aggrigator).

Format is intentionally identical to the aggrigator's
``aggrigator/security/webhook_signing.py`` — Stripe-style
``X-Paradise-Signature: t=<unix_ts>,v1=<hex>`` where the MAC is computed
over ``f"{ts}.".encode() + body`` with HMAC-SHA256.

We re-implement the signer (rather than importing from the aggrigator
package) so MDProject doesn't take a Python-level dependency on the
aggrigator codebase. The receiver's verify side does the work; we just
need to produce bytes-identical signatures.

The threat model: timestamp window blocks replay,
constant-time compare blocks timing oracle.
"""

from __future__ import annotations

import hashlib
import hmac
import time

HEADER_NAME = "X-Paradise-Signature"
SIGNATURE_VERSION = "v1"


def sign(*, secret: str, body: bytes, timestamp: int | None = None) -> str:
    """Return the ready-to-attach header value (``t=...,v1=...``)."""
    if not secret:
        raise ValueError(
            "PARADISE_SECRET is empty — refusing to sign with the empty "
            "string. Set it in MDProject .env to the same value as "
            "AGG_PARADISE_SECRET on the aggrigator."
        )
    ts = timestamp if timestamp is not None else int(time.time())
    msg = f"{ts}.".encode() + body
    digest = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return f"t={ts},{SIGNATURE_VERSION}={digest}"
