"""Seed the dev database with realistic portal data. Idempotent.

Usage:
    python manage.py seed_portal
    python manage.py seed_portal --users 30 --tournaments 8
    python manage.py seed_portal --reset     # requires DEBUG=True
"""

import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.mail.models import Invite
from core.match.models.match import Match
from core.tournament.models.tournament import (
    InvitedPlayer,
    Player,
    Round,
    Tournament,
)
from core.user.models import User

FIRST_NAMES = [
    "Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Drew",
    "Avery", "Quinn", "Skyler", "Peyton", "Reese", "Harper", "Rowan", "Sage",
    "Parker", "Emery", "Kai", "Dakota", "Charlie", "Finley", "River", "Blake",
    "Hayden", "Ellis", "Phoenix", "Remy", "Sidney", "Tatum",
]
LAST_NAMES = [
    "Anderson", "Brooks", "Carter", "Diaz", "Ellis", "Foster", "Garcia", "Hughes",
    "Iverson", "Johnson", "Khan", "Lopez", "Mitchell", "Nguyen", "O'Brien",
    "Patel", "Quinn", "Reyes", "Smith", "Tanaka", "Ulrich", "Vasquez",
    "Williams", "Xu", "Young", "Zimmerman",
]
BIO_SNIPPETS = [
    "Lifelong sports fan. Love a fair bracket.",
    "Weekend warrior. Better at picks than I am at calls.",
    "Here for the banter.",
    "Mostly in it for the trophy screenshot.",
    "Long-time lurker, first-time bracketeer.",
    "Can't stop, won't stop.",
    "Watching too much film. Still losing.",
    "Bench coach energy.",
]


class Command(BaseCommand):
    help = "Seed the portal with realistic dev data. Idempotent."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=20)
        parser.add_argument("--tournaments", type=int, default=8)
        parser.add_argument("--matches", type=int, default=40)
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Wipe seeded data first (DEBUG=True required).",
        )

    @transaction.atomic
    def handle(self, *, users, tournaments, matches, reset, **_):
        if reset:
            if not settings.DEBUG:
                raise CommandError("--reset requires DEBUG=True")
            self._wipe()

        admin = self._ensure_admin()
        players = self._ensure_players(n=users)
        self._wire_friendships(players)

        tournaments_built = self._build_tournament_mix(players, count=tournaments)
        matches_built = self._build_standalone_matches(players, count=matches)
        invites_built = self._ensure_invite_inbox(players)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(players)} players (+1 admin), "
                f"{len(tournaments_built)} tournaments, "
                f"{matches_built} standalone matches, "
                f"{invites_built} match invites."
            )
        )
        self.stdout.write(
            "Dev login: admin@example.com / admin   |   "
            "playerNNN@example.com / portal-dev-pass"
        )

    # ── helpers ──────────────────────────────────────────────

    def _ensure_admin(self):
        # Reuse any existing staff superuser rather than forcing a new one.
        existing = User.objects.filter(is_staff=True, is_superuser=True).first()
        if existing:
            return existing
        admin = User.objects.create(
            email="admin@example.com",
            username="admin",
            is_staff=True,
            is_superuser=True,
            is_active=True,
            first_name="Dev",
            last_name="Admin",
        )
        admin.set_password("admin")
        admin.save()
        return admin

    def _ensure_players(self, *, n):
        players = []
        for i in range(n):
            email = f"player{i:03d}@example.com"
            username = f"player{i:03d}"
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": username,
                    "first_name": first,
                    "last_name": last,
                    "bio": random.choice(BIO_SNIPPETS),
                    "is_active": True,
                },
            )
            if created:
                user.set_password("portal-dev-pass")
                user.save()
            players.append(user)
        return players

    def _wire_friendships(self, players):
        for p in players:
            existing = p.friends.count()
            if existing >= 3:
                continue
            target = random.randint(3, 8)
            need = max(0, target - existing)
            pool = [u for u in players if u != p and not p.friends.filter(pk=u.pk).exists()]
            sample = random.sample(pool, k=min(need, len(pool)))
            p.friends.add(*sample)

    def _build_tournament_mix(self, players, *, count):
        """8 tournaments covering every state. First N honoured."""
        specs = [
            ("Spring Shootout",     "created",    0,  16),
            ("Rising Stars Cup",    "created",    5,  16),
            ("Ready Set Go",        "created",    16, 16),
            ("Midseason Clash",     "inprogress", 16, 16),
            ("Finals Warmup",       "inprogress", 8,  8),
            ("Last Year's Crown",   "completed",  32, 32),
            ("Cancelled Invite",    "aborted",    4,  16),
            ("Quick Showcase",      "created",    2,  4),
        ]
        built = []
        for name, state, accepted, max_n in specs[:count]:
            t = self._build_single_tournament(name, state, accepted, max_n, players)
            if t:
                built.append(t)
        return built

    def _build_single_tournament(self, name, state, accepted, max_n, players):
        if Tournament.objects.filter(name=name).exists():
            return Tournament.objects.get(name=name)  # idempotent

        # Bypass the manager's create() which expects a naive datetime — go
        # through the model directly so we don't fight make_aware().
        start = timezone.now() + timedelta(days=random.randint(-30, 30))
        t = Tournament(
            name=name,
            start_date=start,
            max_accepted_players=max_n,
        )
        t.save()

        roster = random.sample(players, k=min(accepted, len(players)))
        for user in roster:
            Player.objects.create(tournament=t, player=user)

        if state in ("inprogress", "completed"):
            try:
                Tournament.objects.bracket_maker(t)
            except Exception as exc:
                self.stderr.write(f"  bracket_maker failed for '{name}': {exc}")
                t.state = "created"
                t.save()
                return t
            if state == "completed":
                self._complete_bracket(t)
        elif state == "aborted":
            t.state = "aborted"
            t.save()

        return t

    def _complete_bracket(self, tournament):
        levels = int(tournament.levels)
        for level in range(levels - 1, -1, -1):
            rounds = list(tournament.rounds.filter(level_num=level))
            for r in rounds:
                if not r.player_1 and not r.player_2:
                    continue
                choices = [p for p in (r.player_1, r.player_2) if p]
                r.winner = random.choice(choices)
                r.completed = True
                r.save()
                if r.next_round:
                    nxt = r.next_round
                    if nxt.prev_round_1_id == r.id:
                        nxt.player_1 = r.winner
                    elif nxt.prev_round_2_id == r.id:
                        nxt.player_2 = r.winner
                    nxt.save()

        final = tournament.final_round
        if final and final.winner:
            tournament.winner = final.winner
        tournament.state = "completed"
        tournament.save()

    def _build_standalone_matches(self, players, *, count):
        existing = Match.objects.count()
        if existing >= count:
            return existing

        created = 0
        need = count - existing
        for _ in range(need):
            a, b = random.sample(players, 2)
            try:
                Match.objects.create_match(a, b)
                created += 1
            except Exception as exc:
                self.stderr.write(f"  match create failed: {exc}")
        return existing + created

    def _ensure_invite_inbox(self, players):
        if Invite.objects.filter(state="sent").count() >= 3:
            return Invite.objects.count()

        recipients = random.sample(players, k=min(2, len(players)))
        created = 0
        for recipient in recipients:
            for _ in range(random.randint(1, 3)):
                sender = random.choice([p for p in players if p != recipient])
                if Invite.objects.filter(sender=sender, player=recipient, state="sent").exists():
                    continue
                Invite.objects.create(
                    sender=sender,
                    player=recipient,
                    invited_date=timezone.now(),
                    state="sent",
                    type="match",
                )
                created += 1
        return created

    def _wipe(self):
        self.stdout.write(self.style.WARNING("Wiping seeded data…"))
        Invite.objects.all().delete()
        Match.objects.all().delete()
        Round.objects.all().delete()
        Player.objects.all().delete()
        InvitedPlayer.objects.all().delete()
        Tournament.objects.all().delete()
        User.objects.filter(email__startswith="player").delete()
