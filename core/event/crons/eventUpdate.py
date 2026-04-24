import logging

from core.event.models.event import Event
from core.event.models.sport import Sport
from core.event.models.team import Team
from core.event.sofascore import QuotaExceeded, SofaScoreClient

logger = logging.getLogger(__name__)


# /tournaments/get-scheduled-events returns empty for some sports on the
# current RapidAPI plan (observed: ice hockey id=4). Fall back to
# /tournaments/get-live-events by sport slug for these cases.
LIVE_ONLY_FALLBACK = {
    4: "ice-hockey",
}


class EventCron:
    """Ingests scheduled events + embedded teams from SofaScore.

    One API call per sport per tick. Teams are extracted from the event
    payload — no separate team API call.
    """

    def __init__(self, client=None):
        self.client = client or SofaScoreClient()

    def _fetch_events(self, sport):
        try:
            payload = self.client.get_scheduled_sport_events(sport.id)
        except QuotaExceeded as exc:
            logger.error("Skipping sport %s: %s", sport, exc)
            return None

        events = (payload or {}).get("events") or []
        if events or sport.id not in LIVE_ONLY_FALLBACK:
            return payload

        # Fallback to live events for sports whose scheduled endpoint is empty
        slug = LIVE_ONLY_FALLBACK[sport.id]
        logger.info(
            "Scheduled events empty for sport=%s; falling back to live-events?sport=%s",
            sport.id, slug,
        )
        try:
            return self.client.get_live_sport_events(slug)
        except QuotaExceeded as exc:
            logger.error("Skipping sport %s live fallback: %s", sport, exc)
            return payload

    def ingest_sport(self, sport):
        payload = self._fetch_events(sport)

        if not payload:
            return 0

        events = payload.get("events") or []
        ingested = 0
        for ev in events:
            home_payload = ev.get("homeTeam")
            away_payload = ev.get("awayTeam")
            if not home_payload or not away_payload:
                continue

            home = Team.objects.upsert_from_payload(home_payload, sport=sport)
            away = Team.objects.upsert_from_payload(away_payload, sport=sport)
            Event.objects.upsert_from_payload(ev, sport=sport, home=home, away=away)
            ingested += 1
        return ingested

    def update_all_events(self):
        total = 0
        for sport in Sport.objects.filter(active=True):
            total += self.ingest_sport(sport)
        return total


def update_all_events():
    EventCron().update_all_events()
