"""Pick of the Day views (plan Phase 6).

- ``make_pick``: one-tap pick endpoint hit from the dashboard card.
- ``leaderboard``: daily winners + streak + total-wins boards.
"""

from __future__ import annotations

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from core.event.odds.humanize import humanize_selection
from core.potd.models import (
    DailyPick, DailyPickResult, PickError, PickOfDay, potd_today,
)
from core.ratelimit import rate_limit


# Card ordering: home side, then the draw (3-way soccer lines), then away.
_SELECTION_ORDER = {"HOME": 0, "DRAW": 1, "AWAY": 2}


def potd_card_context(user):
    """Dashboard-card context: today's pick, its selections (humanized,
    HOME → DRAW → AWAY), the user's pick if any. Selections come from the
    locally mirrored market — no aggregator round-trip on dashboard render."""
    potd = PickOfDay.objects.for_today()
    if potd is None:
        return {"potd": None}
    selections = sorted(
        potd.market.selections.select_related(
            "market", "market__event",
            "market__event__home_team", "market__event__away_team",
        ),
        key=lambda s: (_SELECTION_ORDER.get(s.type, 9), s.type),
    )
    options = [
        {"id": s.id, "label": humanize_selection(s), "odds": s.decimal_odds}
        for s in selections
    ]
    user_pick = DailyPick.objects.filter(user=user, potd=potd).select_related(
        "selection", "selection__market", "selection__market__event",
        "selection__market__event__home_team",
        "selection__market__event__away_team",
    ).first()
    return {
        "potd": potd,
        "potd_options": options,
        "potd_user_pick": user_pick,
        "potd_user_pick_label": humanize_selection(user_pick.selection) if user_pick else None,
        "potd_locked": potd.is_locked,
        "potd_streak": user.potd_current_streak,
    }


@require_POST
@login_required(login_url='/auth/login/')
@rate_limit("potd-pick", 20, 3600, per="user")
def make_pick(request):
    """POST JSON {"selection_id": ...} — pick on today's PotD."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid request data.'}, status=400)

    selection_id = (data.get('selection_id') or '').strip()
    if not selection_id:
        return JsonResponse({'status': 'error', 'message': 'selection_id required.'}, status=400)

    potd = PickOfDay.objects.for_today()
    if potd is None:
        return JsonResponse({'status': 'error', 'message': "There's no Pick of the Day today."}, status=404)

    selection = potd.market.selections.filter(pk=selection_id).first()
    if selection is None:
        return JsonResponse({'status': 'error', 'message': "That selection isn't part of today's pick."}, status=400)

    try:
        DailyPick.objects.record_pick(user=request.user, potd=potd, selection=selection)
    except PickError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)

    return JsonResponse({
        'status': 'success',
        'streak': request.user.potd_current_streak,
    })


@login_required(login_url='/auth/login/')
def leaderboard(request):
    """Daily + streak + total-wins leaderboards. Results sync lazily here
    (settlement has no signal), so the page is correct even between crons."""
    DailyPick.objects.sync_pending()
    User = get_user_model()
    today = potd_today()

    # Most recent day with settled results — today once its event settles,
    # else look back a few days (quiet slates, postponements).
    daily_day = None
    daily_winners = []
    for offset in range(0, 4):
        day = today - timedelta(days=offset)
        winners = list(
            DailyPick.objects.filter(potd__date=day, result=DailyPickResult.WON)
            .select_related(
                "user", "selection", "selection__market",
                "selection__market__event",
                "selection__market__event__home_team",
                "selection__market__event__away_team",
            )
            .order_by("created_at")[:50]
        )
        if winners:
            daily_day, daily_winners = day, winners
            break
    daily_winners = [
        {"user": p.user, "label": humanize_selection(p.selection)}
        for p in daily_winners
    ]

    streak_board = list(
        User.objects.filter(potd_current_streak__gt=0)
        .order_by("-potd_current_streak", "-potd_best_streak", "username")[:25]
    )
    wins_board = list(
        User.objects.annotate(
            potd_wins=Count("daily_picks", filter=Q(daily_picks__result=DailyPickResult.WON)),
        )
        .filter(potd_wins__gt=0)
        .order_by("-potd_wins", "username")[:25]
    )

    potd = PickOfDay.objects.for_today()
    context = {
        "potd": potd,
        "potd_pick_count": potd.picks.count() if potd else 0,
        "daily_day": daily_day,
        "daily_winners": daily_winners,
        "streak_board": streak_board,
        "wins_board": wins_board,
    }
    return render(request, "portal/potd/leaderboard.html", context)
