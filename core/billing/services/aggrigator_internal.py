"""Thin client for the aggrigator's signed Paradise channel.

Three operations, all HMAC-signed via ``X-Paradise-Signature``:

- ``provision_user(user)`` — POST /v1/internal/users. Idempotent. Returns
  the plaintext API key when the row is newly minted (201), empty string
  when the user already existed (200).
- ``sync_entitlement(user, *, tier, status, features)`` — PATCH
  /v1/internal/users/{external_user_id}/entitlements. Re-sends the
  current truth so the aggrigator's mirror matches MDProject's.
- ``rotate_api_key(user)`` — POST .../api-keys/rotate. Revokes every
  live key and mints a fresh one. Returns the plaintext.

Failure modes:
- HTTP errors raise ``ParadiseError`` (callers decide whether to retry).
- Missing ``PARADISE_SECRET`` raises ``ImproperlyConfigured`` at sign
  time — surfaced to operator, not silently dropped.
- Missing ``AGGRIGATOR_BASE_URL`` raises ``ImproperlyConfigured`` too.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from core.billing.services.paradise_signing import HEADER_NAME, sign

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10.0  # seconds


class ParadiseError(Exception):
    """Any non-2xx response from the aggrigator's /v1/internal/* surface."""


def _base_url() -> str:
    base = (getattr(settings, "AGGRIGATOR_BASE_URL", "") or "").rstrip("/")
    if not base:
        raise ImproperlyConfigured(
            "AGGRIGATOR_BASE_URL is not set in MDProject settings — "
            "Paradise calls cannot be made."
        )
    return base


def _secret() -> str:
    secret = getattr(settings, "PARADISE_SECRET", "") or ""
    if not secret:
        raise ImproperlyConfigured(
            "PARADISE_SECRET is not set in MDProject settings — refusing "
            "to call /v1/internal/* without HMAC. Set it to the same "
            "value as the aggrigator's AGG_PARADISE_SECRET."
        )
    return secret


def _signed_request(method: str, path: str, body: dict[str, Any]) -> requests.Response:
    """POST/PATCH a JSON body with the Paradise HMAC header attached.

    Caller is responsible for status-code handling — this returns the raw
    Response so the caller can distinguish 200 vs 201 (provisioning uses
    the difference to know whether to expect a fresh ``api_key``).
    """
    raw = json.dumps(body).encode()
    headers = {
        HEADER_NAME: sign(secret=_secret(), body=raw),
        "Content-Type": "application/json",
    }
    url = f"{_base_url()}{path}"
    try:
        resp = requests.request(method, url, data=raw, headers=headers, timeout=_DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        raise ParadiseError(f"transport error on {method} {path}: {exc}") from exc
    return resp


# ---- public API --------------------------------------------------------


def provision_user(user, *, tier: str = "FREE", features: dict | None = None) -> str:
    """Idempotently provision ``user`` in the aggrigator.

    Returns the plaintext API key when the row is newly minted (201) and
    an empty string when the user already existed (200). Either way the
    caller should overwrite ``user.aggrigator_api_key`` only when the
    returned value is non-empty.
    """
    body = {
        "external_user_id": str(user.public_id),
        "email": user.email,
        "tier": tier,
        "features": features or {"analytics": tier == "PRO"},
    }
    resp = _signed_request("POST", "/v1/internal/users", body)
    if resp.status_code not in (200, 201):
        raise ParadiseError(
            f"provision_user({user.pk}) -> {resp.status_code}: {resp.text[:200]}"
        )
    data = resp.json()
    return data.get("api_key", "") if resp.status_code == 201 else ""


def sync_entitlement(
    user, *, tier: str, status: str, features: dict | None = None,
) -> None:
    """Push current tier/status to the aggrigator's mirror.

    Called from the Stripe webhook handler whenever Stripe reports a
    subscription state change. Re-sending the same body is a no-op apart
    from the ``updated`` timestamp on the aggrigator side.
    """
    body = {
        "tier": tier,
        "status": status,
        "features": features or {"analytics": tier == "PRO"},
    }
    path = f"/v1/internal/users/{user.public_id}/entitlements"
    resp = _signed_request("PATCH", path, body)
    if resp.status_code != 200:
        raise ParadiseError(
            f"sync_entitlement({user.pk}) -> {resp.status_code}: {resp.text[:200]}"
        )


def rotate_api_key(user) -> str:
    """Mint a new API key for ``user``, revoking the old one. Returns plaintext."""
    path = f"/v1/internal/users/{user.public_id}/api-keys/rotate"
    resp = _signed_request("POST", path, {})
    if resp.status_code != 201:
        raise ParadiseError(
            f"rotate_api_key({user.pk}) -> {resp.status_code}: {resp.text[:200]}"
        )
    return resp.json().get("api_key", "")


@dataclass(frozen=True)
class TenantUserResult:
    """Outcome of ``get_or_create_tenant_user`` — fed to the admin
    Messages framework so the operator sees what actually happened."""
    api_key: str          # the key now stored on User (always non-empty on success)
    external_id: Any      # the public_id we mirrored across (UUID)
    created: bool         # True when the aggrigator row was newly minted (201)
    rotated: bool         # True when we had to rotate because aggrigator already had the user


def get_or_create_tenant_user(
    user, *, tier: str | None = None, features: dict | None = None,
) -> TenantUserResult:
    """Provision the user on the aggrigator and persist the result on the
    User row. Mirrors the per-user logic in the ``backfill_aggrigator_users``
    management command so the admin "Provision aggrigator user" button
    and the bulk backfill stay in lock-step.

    Flow:
    1. Call ``provision_user``. If the aggrigator was empty for this
       ``external_user_id`` (201) we get the plaintext key back — save it.
    2. If the aggrigator already had the row (200, empty ``api_key``),
       we have no key on this side either — call ``rotate_api_key`` to
       force-mint a fresh one. The old aggrigator-side keys are
       revoked, which is the right call: any key we don't have stored
       can't be served by MDProject anyway.

    Tier defaults to the user's current Subscription plan code (PRO /
    FREE) when not passed. Falls back to FREE if there's no
    Subscription row yet — the admin never has to think about which
    tier value is "right"."""
    from core.user.models import User as UserModel  # avoid circular import at module load

    resolved_tier = (tier or _current_tier(user)).upper()
    resolved_features = features or {"analytics": resolved_tier == "PRO"}

    key = provision_user(user, tier=resolved_tier, features=resolved_features)
    rotated = False
    created = bool(key)
    if not key:
        # 200 path — aggrigator already had the row but MDProject has no
        # stored key. Rotate to recover a usable key.
        key = rotate_api_key(user)
        rotated = True

    if not key:
        raise ParadiseError(
            f"get_or_create_tenant_user({user.pk}): aggrigator returned "
            "no api_key after provision+rotate — manual intervention needed."
        )

    UserModel.objects.filter(pk=user.pk).update(
        aggrigator_api_key=key,
        aggrigator_external_id=user.public_id,
    )
    user.aggrigator_api_key = key
    user.aggrigator_external_id = user.public_id
    logger.info(
        "aggrigator tenant_user %s for user_id=%s email=%s",
        "created" if created else ("rotated" if rotated else "noop"),
        user.pk, user.email,
    )
    return TenantUserResult(
        api_key=key,
        external_id=user.public_id,
        created=created,
        rotated=rotated,
    )


def _current_tier(user) -> str:
    """Read the user's current Subscription tier (PRO / FREE) for
    aggrigator entitlement payloads. Defaults to FREE if the user has
    no subscription row, which matches the signup default."""
    sub = getattr(user, "subscription", None)
    plan = getattr(sub, "plan", None) if sub else None
    code = getattr(plan, "code", None) if plan else None
    return code or "FREE"
