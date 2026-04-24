from django.utils import timezone

from core.match.models import Match


class MatchCron:
    def completeMatches(self):
        cutoff = timezone.now()
        matches = Match.objects.filter(end_date__lte=cutoff, match_state="accepted")
        if not matches.exists():
            print("No matches found.")
            return
        for match in matches:
            Match.objects.maybe_complete_match(match)
