import logging
import os
from datetime import datetime

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)


MONTHLY_CAP = 500
SOFT_LIMIT = 480


class QuotaExceeded(Exception):
    pass


class SofaScoreClient:
    # domain = "https://sofascore.p.rapidapi.com"
    domain = "http://127.0.0.1:8765"


    def __init__(self):
        self.headers = {
            "x-rapidapi-key": os.getenv("RAPID_API_KEY", ""),
            "x-rapidapi-host": "sofascore.p.rapidapi.com",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _counter_key():
        return f"sofascore:calls:{datetime.utcnow():%Y-%m}"

    @classmethod
    def calls_this_month(cls):
        return cache.get(cls._counter_key(), 0)

    def _request(self, path, params):
        key = self._counter_key()
        used = cache.get(key, 0)
        if used >= SOFT_LIMIT:
            raise QuotaExceeded(
                f"SofaScore monthly quota at {used}/{MONTHLY_CAP}; refusing call to {path}"
            )

        url = f"{self.domain}{path}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
        except requests.RequestException as exc:
            logger.error("SofaScore request failed: %s %s — %s", path, params, exc)
            return None

        cache.set(key, used + 1, timeout=60 * 60 * 24 * 40)

        if response.status_code != 200:
            logger.error(
                "SofaScore %s returned %s: %s", path, response.status_code, response.text[:200]
            )
            return None
        return response.json()

    def get_sports_list(self, country=""):
        return self._request("/sports/list", {"countryCode": country})

    def get_scheduled_sport_events(self, sport_id):
        return self._request(
            "/tournaments/get-scheduled-events", {"categoryId": str(sport_id)}
        )

    def get_live_sport_events(self, sport_slug):
        return self._request("/tournaments/get-live-events", {"sport": sport_slug})

    def get_match_details(self, match_id):
        return self._request("/matches/detail", {"matchId": str(match_id)})

    def get_match_odds(self, match_id):
        return self._request("/matches/get-all-odds", {"matchId": str(match_id)})
