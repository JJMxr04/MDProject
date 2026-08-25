"""Seeds Sport + League tables from SportsGameOdds.

Single shot — call once on deploy. The 8 leagues we cover on the Amateur tier
(MLB, NBA, NCAAB, NCAAF, NFL, NHL, MLS, UEFA_CHAMPIONS_LEAGUE) get
``active=True`` by default with cadences tuned per real usage data.
"""

from django.core.management.base import BaseCommand

from core.event.models import League, Sport
from core.event.providers import get_events_client

# leagueID -> default refresh cadence (minutes). Numbers come from the budget
# math worked out earlier; tune via admin once we have real usage data.
DEFAULT_ACTIVE_LEAGUES: dict[str, int] = {
    "NFL": 720,
    "NBA": 360,
    "MLB": 720,
    "NHL": 720,
    "NCAAF": 1440,
    "NCAAB": 1440,
    "MLS": 1440,
    "UEFA_CHAMPIONS_LEAGUE": 1440,
}


class Command(BaseCommand):
    help = "Seed/refresh Sport + League tables from SportsGameOdds (2 API calls)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--activate",
            nargs="*",
            default=None,
            help=(
                "Override default active leagueIDs. Each must exist in the SGO "
                "league list. Cadence stays at the existing/default value."
            ),
        )
        parser.add_argument(
            "--deactivate-others",
            action="store_true",
            help="Set active=False on every league not in --activate (or DEFAULT).",
        )

    def handle(self, *args, **options):
        active_set = (
            set(options["activate"]) if options["activate"] is not None
            else set(DEFAULT_ACTIVE_LEAGUES.keys())
        )
        deactivate_others = options["deactivate_others"]

        client = get_events_client()

        sports_payload = client.get_sports()
        for sport_dict in sports_payload:
            Sport.objects.upsert_from_sgo(sport_dict)

        # SGO's leagues endpoint is filtered per-sport. Walk every sport so we
        # pick up every league we have access to (bounded by tier).
        seeded = 0
        for sport_dict in sports_payload:
            sport_id = sport_dict.get("sportID")
            if not sport_id:
                continue
            try:
                leagues_payload = client.get_leagues(sport_id=sport_id)
            except Exception as exc:  # noqa: BLE001 — keep walking other sports
                self.stderr.write(f"  skipping sport={sport_id}: {exc}")
                continue
            for league_dict in leagues_payload:
                # Some sports' league rows omit sportID; backfill from the parent.
                league_dict.setdefault("sportID", sport_id)
                league = League.objects.upsert_from_sgo(league_dict)
                if league is None:
                    continue
                seeded += 1

                if league.id in active_set:
                    cadence = DEFAULT_ACTIVE_LEAGUES.get(
                        league.id, league.refresh_cadence_minutes
                    )
                    if (not league.active) or league.refresh_cadence_minutes != cadence:
                        league.active = True
                        league.refresh_cadence_minutes = cadence
                        league.save(update_fields=["active", "refresh_cadence_minutes"])
                elif deactivate_others and league.active:
                    league.active = False
                    league.save(update_fields=["active"])

        rollups = (
            League.objects.filter(active=True)
            .values_list("id", "sport_id", "refresh_cadence_minutes")
        )
        self.stdout.write(
            f"Seeded {seeded} leagues. Active ({len(rollups)}): "
            + ", ".join(
                f"{lid}({sid}, {c}m)" for lid, sid, c in sorted(rollups)
            )
        )

        # Sport.active is a rollup of per-league activity.
        for sport in Sport.objects.all():
            should_be_active = sport.leagues.filter(active=True).exists()
            if sport.active != should_be_active:
                sport.active = should_be_active
                sport.save(update_fields=["active"])
