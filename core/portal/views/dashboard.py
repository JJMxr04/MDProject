from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from core.mail.models import Invite
from core.match.models.match import Match
from core.tournament.models.tournament import Tournament


@login_required(login_url="/auth/login/")
def portal_dashboard(request):
    user = request.user
    now = timezone.now()

    # ── stats ──────────────────────────────────────────────────
    matches_qs = Match.objects.filter(Q(player_1=user) | Q(player_2=user))
    active_match_count = matches_qs.exclude(match_state="completed").count()

    upcoming_tournaments = (
        Tournament.objects.filter(
            player__player=user, state__in=("created", "inprogress")
        )
        .order_by("start_date")
        .distinct()
    )

    pending_invites = Invite.objects.filter(player=user, state="sent")

    stats = {
        "active_match_count": active_match_count,
        "upcoming_tournament_count": upcoming_tournaments.count(),
        "pending_invite_count": pending_invites.count(),
        "friend_count": user.friends.count(),
    }

    # ── needs-your-attention list ──────────────────────────────
    todo = []
    for invite in pending_invites[:5]:
        todo.append({
            "icon": "envelope-open",
            "text": f"Invite from {invite.sender.username}",
            "cta": "Review",
            "href": reverse("core-portal:invite-list"),
        })

    # ── next tournament (nearest future) ───────────────────────
    next_tournament = upcoming_tournaments.filter(start_date__gte=now).first() \
        or upcoming_tournaments.first()

    # ── recent activity (simple match-derived feed for Phase 1) ─
    activity = _recent_activity(user, since=now - timedelta(days=14), limit=10)

    # ── first-run check ────────────────────────────────────────
    is_first_run = (
        stats["friend_count"] == 0
        and stats["active_match_count"] == 0
        and stats["upcoming_tournament_count"] == 0
    )
    checklist = _first_run_checklist(user) if is_first_run else None

    # ── Pick of the Day card (plan Phase 6) ────────────────────
    from core.potd.views import potd_card_context
    potd_context = potd_card_context(user)

    # ── Progression widget (plan Phase 8) ──────────────────────
    from core.ranking.standings import progress_card_context
    progress_context = progress_card_context(user)

    return render(request, "portal/dashboard/dashboard.html", {
        "stats": stats,
        "todo": todo,
        "next_tournament": next_tournament,
        "activity": activity,
        "is_first_run": is_first_run,
        "checklist": checklist,
        **potd_context,
        **progress_context,
    })


def _recent_activity(user, *, since, limit):
    events = []
    recent_matches = (
        Match.objects.filter(Q(player_1=user) | Q(player_2=user))
        .filter(updated__gte=since)
        .order_by("-updated")[:limit]
    )
    for m in recent_matches:
        opponent = m.player_2 if m.player_1_id == user.id else m.player_1
        if m.match_state == "completed":
            won = (m.winner_id == user.id)
            events.append({
                "icon": "check2-circle" if won else "dash-circle",
                "text": f"{'Won' if won else 'Lost'} match against {opponent.username if opponent else '—'}",
                "at": m.updated,
            })
        elif m.match_state == "accepted":
            events.append({
                "icon": "controller",
                "text": f"Match started with {opponent.username if opponent else '—'}",
                "at": m.updated,
            })
    return events[:limit]


def _first_run_checklist(user):
    return [
        {"key": "profile", "label": "Complete your profile",
         "done": bool(user.first_name and user.last_name and user.bio),
         "href": reverse("core-portal:profile")},
        {"key": "friends", "label": "Add your first friend",
         "done": user.friends.exists(),
         "href": reverse("core-portal:friend_search")},
        {"key": "match", "label": "Create or accept a match",
         "done": Match.objects.filter(Q(player_1=user) | Q(player_2=user)).exists(),
         "href": reverse("core-portal:portal-public-match-list")},
        {"key": "tournament", "label": "Join a tournament",
         "done": False,  # no user-facing tournament join flow yet
         "href": reverse("core-portal:core-portal-tournament:portal-my-tournaments")},
    ]
