import logging

from django.utils import timezone

from core.match.models import Match

logger = logging.getLogger(__name__)


class MatchCron:
    def completeMatches(self):
        cutoff = timezone.now()
        matches = Match.objects.filter(end_date__lte=cutoff, match_state="accepted")
        if not matches.exists():
            logger.info("completeMatches: no matches due")
            return
        for match in matches:
            Match.objects.maybe_complete_match(match)
