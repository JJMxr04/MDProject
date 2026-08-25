"""SportsGameOdds API client.

Modeled on the fixture-saving client from an earlier prototype
(``sports-scores/api/sports_game.py``), adapted for Django: env
vars come through ``os.environ``, throttling/quota state sits in the Django
cache so multiple Celery workers share it.

Fixture mode: when settings/env ``SPORTSGAMEODDS_FIXTURE_DIR`` is set to a
directory, ``_request`` reads canned JSON from disk instead of hitting the API.
The filenames match the simulator's saved files
(``events__league-NFL.json``, ``leagues__sport-FOOTBALL.json``, ``sports.json``,
``usage.json``, ``teams__league-NFL.json``). This lets us develop and exercise
the pipeline against captured payloads without burning the 2,500 entities/month
Amateur quota.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)


# BASE_URL = "https://api.sportsgameodds.com/v2"
BASE_URL = "http://127.0.0.1:8765/v2"

# Amateur tier ceilings, mirrored locally so we can pre-flight calls.
MONTHLY_ENTITY_CAP = 2500
MONTHLY_ENTITY_SOFT_LIMIT_PCT = 0.95  # refuse cron calls past 95% used.

# Token bucket: 10 tokens, 1 every 6s. Implemented in cache so workers share it.
PER_MINUTE_REQUESTS = 10


class SportsGameOddsError(Exception):
    """Raised for any non-recoverable provider failure."""


class QuotaExceeded(SportsGameOddsError):
    """Raised when the monthly entity counter is past the soft limit."""


class SportsGameOddsClient:
    """Thin client over ``api.sportsgameodds.com/v2``.

    Public surface is cursor-aware: callers ask for ``get_events(...)`` and get
    back a generator that walks every page transparently.
    """

    def __init__(
        self,
        api_key: str | None = None,
        session: requests.Session | None = None,
        fixture_dir: str | os.PathLike | None = None,
        soft_limit_pct: float = MONTHLY_ENTITY_SOFT_LIMIT_PCT,
    ) -> None:
        self.api_key = api_key or os.environ.get("SPORTSGAMEODDS_API_KEY", "")
        self.session = session or requests.Session()
        if self.api_key:
            self.session.headers["x-api-key"] = self.api_key

        fixture = fixture_dir or os.environ.get("SPORTSGAMEODDS_FIXTURE_DIR", "")
        self.fixture_dir = Path(fixture) if fixture else None

        if not self.fixture_dir and not self.api_key:
            # Either real key or fixture mode is required. Don't crash on import,
            # but every request will fail loudly.
            logger.warning(
                "SportsGameOddsClient initialized with neither SPORTSGAMEODDS_API_KEY "
                "nor SPORTSGAMEODDS_FIXTURE_DIR set; calls will fail."
            )

        self.soft_limit_pct = soft_limit_pct

    # ---- counter helpers --------------------------------------------------

    @staticmethod
    def _entity_counter_key() -> str:
        return f"sgo:entities:{datetime.utcnow():%Y-%m}"

    @classmethod
    def entities_this_month(cls) -> int:
        return cache.get(cls._entity_counter_key(), 0)

    def _bump_entities(self, n: int) -> None:
        if n <= 0:
            return
        key = self._entity_counter_key()
        try:
            new_value = cache.incr(key, n)
        except ValueError:
            cache.set(key, n, timeout=60 * 60 * 24 * 40)
            new_value = n
        if new_value >= MONTHLY_ENTITY_CAP * self.soft_limit_pct:
            logger.warning(
                "SGO entity counter at %d/%d (>=%.0f%%); future ingest calls will be refused.",
                new_value, MONTHLY_ENTITY_CAP, self.soft_limit_pct * 100,
            )

    def _check_entity_cap(self) -> None:
        if self.fixture_dir is not None:
            return  # fixture mode bypasses the cap
        used = self.entities_this_month()
        if used >= MONTHLY_ENTITY_CAP * self.soft_limit_pct:
            raise QuotaExceeded(
                f"SGO entity counter at {used}/{MONTHLY_ENTITY_CAP}; refusing call."
            )

    # ---- token bucket -----------------------------------------------------

    @staticmethod
    def _bucket_key() -> str:
        return "sgo:bucket"

    def _consume_token(self) -> None:
        """Token bucket: 10 capacity, 1 token / 6s.

        Cheap and good enough — under contention multiple workers may briefly
        exceed 10/min, but the API responds 429 and we back off.
        """
        if self.fixture_dir is not None:
            return
        key = self._bucket_key()
        now = time.monotonic()
        state = cache.get(key) or {"tokens": float(PER_MINUTE_REQUESTS), "ts": now}
        elapsed = max(0.0, now - state["ts"])
        tokens = min(float(PER_MINUTE_REQUESTS), state["tokens"] + elapsed * (PER_MINUTE_REQUESTS / 60.0))
        if tokens < 1.0:
            wait = (1.0 - tokens) * (60.0 / PER_MINUTE_REQUESTS)
            logger.debug("SGO bucket empty; sleeping %.2fs", wait)
            time.sleep(wait)
            tokens = 1.0
            now = time.monotonic()
        cache.set(key, {"tokens": tokens - 1.0, "ts": now}, timeout=120)

    # ---- transport --------------------------------------------------------

    def _fixture_path(self, path: str, params: dict[str, Any]) -> Path | None:
        if self.fixture_dir is None:
            return None
        path = path.strip("/")
        if path == "sports":
            return self.fixture_dir / "sports.json"
        if path == "account/usage":
            return self.fixture_dir / "usage.json"
        if path == "leagues":
            sport = params.get("sportID")
            return self.fixture_dir / (f"leagues__sport-{sport}.json" if sport else "leagues__all.json")
        if path == "events":
            league = params.get("leagueID")
            return self.fixture_dir / (f"events__league-{league}.json" if league else "events__all.json")
        if path == "teams":
            league = params.get("leagueID")
            return self.fixture_dir / (f"teams__league-{league}.json" if league else "teams__all.json")
        if path == "players":
            team = params.get("teamID")
            return self.fixture_dir / (f"players__team-{team}.json" if team else "players__all.json")
        return None

    def _request(self, path: str, params: dict[str, Any] | None = None) -> dict:
        params = {k: v for k, v in (params or {}).items() if v is not None}
        fixture = self._fixture_path(path, params)
        if fixture is not None:
            if not fixture.exists():
                raise SportsGameOddsError(f"Fixture not found: {fixture}")
            logger.debug("SGO fixture read: %s", fixture)
            return json.loads(fixture.read_text())

        if not self.api_key:
            raise SportsGameOddsError("SPORTSGAMEODDS_API_KEY is unset")

        self._check_entity_cap()
        self._consume_token()

        url = f"{BASE_URL}/{path.lstrip('/')}"
        try:
            response = self.session.get(url, params=params, timeout=30)
        except requests.RequestException as exc:
            raise SportsGameOddsError(f"GET {path} failed: {exc}") from exc

        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After") or 6.0)
            logger.warning("SGO 429; sleeping %.1fs and retrying %s", retry_after, path)
            time.sleep(retry_after)
            return self._request(path, params)

        if response.status_code >= 400:
            raise SportsGameOddsError(
                f"GET {path} returned {response.status_code}: {response.text[:200]}"
            )

        body = response.json()
        if body.get("success") is False:
            raise SportsGameOddsError(body.get("error", "Unknown SGO error"))

        # Bump the entity counter by the size of `data` (list payloads).
        data = body.get("data")
        if isinstance(data, list):
            self._bump_entities(len(data))
        elif data is not None:
            self._bump_entities(1)

        return body

    # ---- public surface ---------------------------------------------------

    def get_account_usage(self) -> dict:
        return self._request("account/usage").get("data") or {}

    def get_sports(self) -> list[dict]:
        return self._request("sports").get("data") or []

    def get_leagues(self, sport_id: str | None = None) -> list[dict]:
        return self._request("leagues", {"sportID": sport_id}).get("data") or []

    def get_teams(self, league_id: str) -> list[dict]:
        # Single-page; teams lists are small enough on Amateur tier.
        return self._request("teams", {"leagueID": league_id, "limit": 100}).get("data") or []

    def get_events(
        self,
        *,
        league_id: str | None = None,
        event_id: str | None = None,
        starts_after: str | None = None,
        starts_before: str | None = None,
        live: bool | None = None,
        finalized: bool | None = None,
        odds_available: bool | None = True,
        odd_ids: list[str] | None = None,
        include_open_close: bool | None = None,
        include_opposing_odds: bool | None = None,
        include_alt_lines: bool | None = None,
        bookmaker_id: str | None = None,
        limit: int = 50,
        max_pages: int | None = None,
    ) -> Iterator[dict]:
        """Cursor-paginated event walker.

        Yields one event dict at a time across all pages. The caller decides
        when to stop (e.g., by breaking on ``starts_before``); we just walk.
        """
        params: dict[str, Any] = {
            "leagueID": league_id,
            "eventID": event_id,
            "startsAfter": starts_after,
            "startsBefore": starts_before,
            "live": _bool_param(live),
            "finalized": _bool_param(finalized),
            "oddsAvailable": _bool_param(odds_available),
            "oddID": ",".join(odd_ids) if odd_ids else None,
            "includeOpenCloseOdds": _bool_param(include_open_close),
            "includeOpposingOdds": _bool_param(include_opposing_odds),
            "includeAltLines": _bool_param(include_alt_lines),
            "bookmakerID": bookmaker_id,
            "limit": limit,
        }

        cursor: str | None = None
        pages = 0
        while True:
            if cursor:
                params["cursor"] = cursor
            body = self._request("events", params)
            for ev in body.get("data") or []:
                yield ev
            cursor = body.get("nextCursor")
            pages += 1
            if not cursor:
                return
            if max_pages is not None and pages >= max_pages:
                return

    def get_event(self, event_id: str, *, include_open_close: bool = True) -> dict | None:
        rows = list(self.get_events(
            event_id=event_id,
            include_open_close=include_open_close,
            include_opposing_odds=True,
            odds_available=None,
            max_pages=1,
        ))
        return rows[0] if rows else None


def _bool_param(value: bool | None) -> str | None:
    if value is None:
        return None
    return "true" if value else "false"
