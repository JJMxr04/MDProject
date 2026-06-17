"""Populate random team colors for local dev.

The matchup color tints only show up when teams actually carry colors, but
the live color sync (Part B follow-on) isn't wired yet. This dev-only command
fills each Team's four color columns with random ``#RRGGBB`` hex so the tints
are visible while testing.

By default it only fills teams whose ``primary_color`` is NULL (idempotent —
re-running won't churn already-coloured teams). ``--overwrite`` re-randomises
every team.

    python manage.py randomize_team_colors
    python manage.py randomize_team_colors --overwrite
"""

from __future__ import annotations

import random

from django.core.management.base import BaseCommand

from core.event.models import Team

_COLOR_FIELDS = ("primary_color", "secondary_color", "primary_contrast", "secondary_contrast")


def _rand_hex() -> str:
    return "#%06x" % random.randint(0, 0xFFFFFF)


class Command(BaseCommand):
    help = (
        "Fill Team color columns with random #RRGGBB hex (dev only). "
        "By default only fills teams with a NULL primary_color; "
        "--overwrite re-randomises every team."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Re-randomise colors for every team, not just NULL ones.",
        )

    def handle(self, *, overwrite, **opts):
        qs = Team.objects.all()
        if not overwrite:
            qs = qs.filter(primary_color__isnull=True)

        updated = 0
        for team in qs.iterator(chunk_size=500):
            for fld in _COLOR_FIELDS:
                setattr(team, fld, _rand_hex())
            team.save(update_fields=list(_COLOR_FIELDS))
            updated += 1

        scope = "all" if overwrite else "null-color"
        self.stdout.write(self.style.SUCCESS(
            f"Randomised colors on {updated} {scope} team(s)."
        ))
