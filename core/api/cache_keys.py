"""Per-user cache key registry (plan 02/09 — no cross-user cache bleed).

Cross-user cache bleed is a *security* bug, not just a correctness one: a cache
key that omits the user id can serve user A's data to user B. Every per-user
cache entry on the v1 surface MUST be keyed through ``user_scoped_key`` so the
user id is structurally part of the key and can't be forgotten.

Catalog/reference data (sports, leagues — identical for everyone) uses
``shared_key`` instead; never put per-user data behind a shared key.
"""

_PREFIX = "v1"


def user_scoped_key(namespace: str, user_id, *parts) -> str:
    """``v1:<namespace>:u<user_id>[:<part>:<part>...]`` — guaranteed user-scoped."""
    key = f"{_PREFIX}:{namespace}:u{user_id}"
    if parts:
        key += ":" + ":".join(str(p) for p in parts)
    return key


def shared_key(namespace: str, *parts) -> str:
    """Catalog/reference key — explicitly NOT user-scoped. Never for user rows."""
    key = f"{_PREFIX}:shared:{namespace}"
    if parts:
        key += ":" + ":".join(str(p) for p in parts)
    return key
