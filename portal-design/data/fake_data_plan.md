# Fake data plan

## Goal

A one-command, idempotent fixture generator that fills the dev database with realistic users, tournaments, matches, rounds, invites, and events so the redesigned templates have something to render. No more empty tables.

---

## Approach — Django management command

Pattern: `core/commands/management/commands/seed_portal.py` (the `core.commands` app is already in `INSTALLED_APPS`). The command is:

- **Idempotent**: running it twice does not duplicate rows. Look up by deterministic keys (`email` for users, `name + start_date` for tournaments).
- **Tunable**: `--users`, `--tournaments`, `--matches`, `--reset` flags.
- **Safe**: `--reset` requires `DEBUG=True` to prevent prod footguns.
- **Offline**: no HTTP calls. Use `Faker` (add to requirements) for names/bios/usernames. Avatars use DiceBear seeds (still offline-capable via data-URLs or skip avatar).

```
venv/bin/python manage.py seed_portal              # sensible defaults
venv/bin/python manage.py seed_portal --reset      # wipe everything (DEBUG only)
venv/bin/python manage.py seed_portal --users 50 --tournaments 8 --matches 40
```

---

## Persona mix

| Persona | Count (default) | Traits |
| --- | --- | --- |
| `admin` | 1 (ensured) | `is_staff=True`, `is_superuser=True`, email `admin@example.com`, password `admin`. |
| `player` | 20 | standard users, random avatars, filled bio. Friend graph wired (each user has 3-8 friends). |
| `writer` | 3 | `is_writer=True`. For testing the "Manage Subscriptions" branch once that feature exists. |
| `viewer` | 5 | users with `is_active=True` but no friends, no matches. For testing empty states. |

Password for all seeded non-admin users: `portal-dev-pass` (documented in `README` / `.env.example`).

---

## Tournament mix

8 tournaments covering every state we need to eyeball:

| # | State | Players (accepted / max) | Rounds progress | Purpose |
| --- | --- | --- | --- | --- |
| 1 | `created` | 0 / 16 | none | Empty-state check on detail page |
| 2 | `created` | 5 / 16 | none | Partial invites pending |
| 3 | `created` | 16 / 16 | ready to start | Shows "Start bracket" CTA |
| 4 | `inprogress` | 16 / 16 | Level 3 of 4 complete | Mid-bracket rendering |
| 5 | `inprogress` | 8 / 8 | Level 0 complete (final about to play) | Close-to-final state |
| 6 | `completed` | 32 / 32 | all rounds complete, winner set | Winner banner + completed bracket |
| 7 | `aborted` | 4 / 16 | never started | Aborted state styling |
| 8 | `created` | 2 / 4 | tiny bracket | Developer-friendly size for quick checks |

Every tournament has a unique `name` like `"Spring Shootout 2026"`, a `start_date` between `now()-30d` and `now()+30d`, and `max_accepted_players` chosen from `{4, 8, 16, 32}`.

---

## Match / Round mix

For each tournament in `inprogress` or `completed`, call `Tournament.objects.bracket_maker(tournament)` — the existing bracket engine already creates `Round` objects and wires `prev_round_1/2` and `next_round`. Then for each round:

- `completed=True`, `winner=random.choice([player_1, player_2])`, matching `Round.match.end_date=now()-random.days(1..14)`.
- Propagate winners up the tree via `round.next_round.player_N = round.winner`.

For **non-tournament matches** (public / friend-invite matches), create ~40 standalone `Match` rows:
- Roughly 60% private (two friends), 30% public open, 10% completed.
- Each has `start_date` within ±14 days of `now()`, random sport.

---

## Invite mix

- 10 `InvitedPlayer` rows in `state='sent'` across the `created` tournaments.
- 5 `Invite` (match invites, `core.mail.models.Invite`) rows in `state='sent'` targeting 2 of the seeded players — so those users have a populated invite bell.

---

## Events (optional, Phase 2)

If `core.event` fixtures are needed:
- 20 upcoming `Event` rows across 3 sports, with `home_team`/`away_team`/`sport_title` fields.
- Used by the tournament round's "golden game" linkage. Only needed for match detail visuals.

Skip in the first seed pass unless `--with-events` is passed.

---

## Data structure diagram

```
User ──< friends >── User
  │
  ├─< InvitedPlayer >── Tournament ──< Round ──> Round (next_round)
  │                          │           │  
  │                          │           └──> Match
  │                          │
  │                          └──< Player  (accepted roster)
  │
  └─< Match.player_1 / player_2

Match ──< Game >── Event
              │
              └── Markets / Outcomes
```

---

## Command skeleton

```python
# core/commands/management/commands/seed_portal.py
import random
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from faker import Faker

from core.user.models import User
from core.tournament.models.tournament import (
    Tournament, InvitedPlayer, Player, Round,
)
from core.match.models.match import Match
from core.mail.models import Invite

fake = Faker()


class Command(BaseCommand):
    help = "Seed the portal with realistic dev data. Idempotent."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=20)
        parser.add_argument("--tournaments", type=int, default=8)
        parser.add_argument("--matches", type=int, default=40)
        parser.add_argument("--reset", action="store_true",
                            help="Wipe seeded data first (DEBUG=True required).")
        parser.add_argument("--with-events", action="store_true")

    @transaction.atomic
    def handle(self, *, users, tournaments, matches, reset, with_events, **_):
        if reset:
            if not settings.DEBUG:
                raise CommandError("--reset requires DEBUG=True")
            self._wipe()

        admin = self._ensure_admin()
        players = self._ensure_players(n=users)
        self._wire_friendships(players)

        tournaments_built = self._build_tournament_mix(players, count=tournaments)
        self._build_standalone_matches(players, count=matches)

        if with_events:
            self._build_events()

        self._ensure_invite_inbox(players)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(players)} players, {len(tournaments_built)} tournaments, "
            f"{matches} standalone matches."
        ))

    # ── helpers ──────────────────────────────────────────────

    def _ensure_admin(self):
        admin, created = User.objects.get_or_create(
            email="admin@example.com",
            defaults={"username": "admin", "is_staff": True, "is_superuser": True,
                      "first_name": "Dev", "last_name": "Admin"},
        )
        if created:
            admin.set_password("admin")
            admin.save()
        return admin

    def _ensure_players(self, *, n):
        players = []
        for i in range(n):
            email = f"player{i:03d}@example.com"
            player, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": fake.unique.user_name(),
                    "first_name": fake.first_name(),
                    "last_name": fake.last_name(),
                    "bio": fake.sentence(nb_words=14),
                },
            )
            if created:
                player.set_password("portal-dev-pass")
                player.save()
            players.append(player)
        return players

    def _wire_friendships(self, players):
        for p in players:
            friends_count = random.randint(3, 8)
            sample = random.sample([u for u in players if u != p],
                                   k=min(friends_count, len(players) - 1))
            p.friends.add(*sample)

    def _build_tournament_mix(self, players, *, count):
        """Spec from fake_data_plan.md: 8 tournaments covering every state."""
        specs = [
            ("Spring Shootout",    "created",    0,  16),
            ("Rising Stars Cup",   "created",    5,  16),
            ("Ready Set Go",       "created",    16, 16),
            ("Midseason Clash",    "inprogress", 16, 16),
            ("Finals Warmup",      "inprogress", 8,  8),
            ("Last Year's Crown",  "completed",  32, 32),
            ("Cancelled Invite",   "aborted",    4,  16),
            ("Quick Showcase",     "created",    2,  4),
        ]
        built = []
        for name, state, accepted, max_n in specs[:count]:
            t = self._build_single_tournament(name, state, accepted, max_n, players)
            built.append(t)
        return built

    def _build_single_tournament(self, name, state, accepted, max_n, players):
        start = timezone.now() + timedelta(days=random.randint(-30, 30))
        t, created = Tournament.objects.get_or_create(
            name=name,
            defaults={"start_date": start, "max_accepted_players": max_n},
        )
        if not created:
            return t  # already seeded

        roster = random.sample(players, k=min(accepted, len(players)))
        for p in roster:
            Player.objects.create(tournament=t, player=p)

        if state == "inprogress" or state == "completed":
            Tournament.objects.bracket_maker(t)
            if state == "completed":
                self._complete_bracket(t)
        elif state == "aborted":
            t.state = "aborted"
            t.save()
        return t

    def _complete_bracket(self, tournament):
        # walk rounds bottom-up, pick winners, propagate.
        for level in range(int(tournament.levels) - 1, -1, -1):
            rounds = tournament.rounds.filter(level_num=level)
            for r in rounds:
                if not r.player_1 and not r.player_2:
                    continue
                r.winner = random.choice([x for x in [r.player_1, r.player_2] if x])
                r.completed = True
                r.save()
                if r.next_round:
                    if r == r.next_round.prev_round_1:
                        r.next_round.player_1 = r.winner
                    else:
                        r.next_round.player_2 = r.winner
                    r.next_round.save()
        # final winner lifts to tournament
        final = tournament.final_round
        if final and final.winner:
            tournament.winner = final.winner
        tournament.state = "completed"
        tournament.save()

    def _build_standalone_matches(self, players, *, count):
        for _ in range(count):
            a, b = random.sample(players, 2)
            Match.objects.create_match(
                a, b,
                start_date=timezone.now() + timedelta(days=random.randint(-14, 14)),
            )

    def _build_events(self):
        pass  # TODO Phase 2; use core.event.models.Event

    def _ensure_invite_inbox(self, players):
        for recipient in random.sample(players, k=min(2, len(players))):
            for _ in range(random.randint(1, 3)):
                sender = random.choice([p for p in players if p != recipient])
                Invite.objects.get_or_create(
                    sender=sender, player=recipient,
                    defaults={"invited_date": timezone.now()},
                )

    def _wipe(self):
        Invite.objects.all().delete()
        Match.objects.all().delete()
        Round.objects.all().delete()
        Player.objects.all().delete()
        InvitedPlayer.objects.all().delete()
        Tournament.objects.all().delete()
        User.objects.filter(email__startswith="player").delete()
```

---

## Tests

A single smoke test in `core/commands/tests.py`:

```python
from django.core.management import call_command
from django.test import TestCase
from core.tournament.models.tournament import Tournament

class SeedPortalTests(TestCase):
    def test_seed_is_idempotent(self):
        call_command("seed_portal", users=5, tournaments=2, matches=3)
        first_count = Tournament.objects.count()
        call_command("seed_portal", users=5, tournaments=2, matches=3)
        self.assertEqual(Tournament.objects.count(), first_count)
```

---

## Next steps after seeding

Once `seed_portal` works:

1. Add to `Makefile`: `make seed` → `venv/bin/python manage.py seed_portal`.
2. Add to CI only for preview-deploy targets, not test runs.
3. Document the seeded credentials in `README.md` under a **"Dev login"** section.
