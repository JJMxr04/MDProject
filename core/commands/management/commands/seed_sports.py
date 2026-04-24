from django.core.management.base import BaseCommand

from core.event.models.sport import Sport
from core.event.sofascore import SofaScoreClient

DEFAULT_ACTIVE_SPORT_IDS = {1, 4, 63}  # soccer (1), ice hockey (4), american football (63)
# Basketball (2) is disabled until the SofaScore odds endpoint returns useful
# BB data — flip back on by running `seed_sports --activate 1 2 4 63`.


class Command(BaseCommand):
    help = "Seed/refresh the Sport table from SofaScore's /sports/list (one API call)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--activate",
            nargs="*",
            type=int,
            default=None,
            help="Override default active sport ids (defaults to 1, 2, 63).",
        )

    def handle(self, *args, **options):
        active_ids = (
            set(options["activate"]) if options["activate"] is not None else DEFAULT_ACTIVE_SPORT_IDS
        )

        client = SofaScoreClient()
        data = client.get_sports_list()
        if not data:
            self.stderr.write("SofaScore /sports/list returned nothing. Aborting.")
            return

        entries = data.get("countrySportPriorities", []) or []
        created_or_updated = 0
        for entry in entries:
            sport_payload = entry.get("sport") or {}
            sport = Sport.objects.upsert_from_payload(sport_payload)
            if sport is None:
                continue
            should_be_active = sport.id in active_ids
            if sport.active != should_be_active:
                sport.active = should_be_active
                sport.save(update_fields=["active"])
            created_or_updated += 1

        active = list(Sport.objects.filter(active=True).values_list("id", "name"))
        self.stdout.write(
            f"Seeded {created_or_updated} sports. Active: {active}"
        )
