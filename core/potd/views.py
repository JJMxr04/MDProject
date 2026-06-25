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
    DailyPick,
    DailyPickResult,
    PickError,
    PickOfDay,
    next_potd_available,
    potd_today,
)
from core.ratelimit import rate_limit

# Card ordering: home side, then the draw (3-way soccer lines), then away.
_SELECTION_ORDER = {"HOME": 0, "DRAW": 1, "AWAY": 2}

# The crowd % split is hidden until enough people have picked, so it never
# looks empty or lopsided (100%/0%) early in the day.
CROWD_THRESHOLD = 10


def _crowd_split(potd, options, user_pick):
    """Social-proof split: per-selection pick counts + share of the day's
    total, the viewer's own side share, and whether we have enough picks to
    show the bar at all (cold-start guard)."""
    counts = {
        row["selection"]: row["n"]
        for row in DailyPick.objects.filter(potd=potd)
        .values("selection")
        .annotate(n=Count("id"))
    }
    total = sum(counts.values())
    sides = []
    for opt in options:
        c = counts.get(opt["id"], 0)
        sides.append({
            "selection_id": opt["id"],
            "label": opt["label"],
            "count": c,
            "pct": round(100 * c / total) if total else 0,
        })
    user_side_pct = None
    if user_pick:
        for s in sides:
            if s["selection_id"] == user_pick.selection_id:
                user_side_pct = s["pct"]
                break
    return {
        "total": total,
        "threshold_met": total >= CROWD_THRESHOLD,
        "sides": sides,
        "user_side_pct": user_side_pct,
    }


def potd_card_context(user):
    """Dashboard-card context: today's pick, its selections (humanized,
    HOME → DRAW → AWAY), the user's pick if any, and the crowd split.
    Selections come from the locally mirrored market — no aggregator
    round-trip on dashboard render."""
    potd = PickOfDay.objects.for_today()
    if potd is None:
        # No pick curated yet today — still surface the countdown so the card
        # can show when the next one opens.
        return {
            "potd": None,
            "potd_streak": user.potd_current_streak,
            "potd_next_at": next_potd_available(),
        }
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
        "crowd": _crowd_split(potd, options, user_pick),
        # When the next day's pick goes live — the card counts down to this
        # once today's pick is settled or closed.
        "potd_next_at": next_potd_available(),
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
        # The shared hype card pinned at the top of the page uses the same
        # context as the dashboard (options, the viewer's pick, crowd split).
        **potd_card_context(request.user),
    }
    return render(request, "portal/potd/leaderboard.html", context)


def _win_streaks(results_chrono):
    """Current + best 'wins in a row'. A LOST breaks the run; VOID/PENDING are
    neutral (skipped) — same philosophy as the picked-day streak."""
    cur = best = 0
    for r in results_chrono:
        if r == DailyPickResult.WON:
            cur += 1
            best = max(best, cur)
        elif r == DailyPickResult.LOST:
            cur = 0
    return cur, best


_RESULT_META = {
    DailyPickResult.WON: ("Won", "success"),
    DailyPickResult.LOST: ("Lost", "danger"),
    DailyPickResult.VOID: ("Void", "muted"),
    DailyPickResult.PENDING: ("Pending", "warning"),
}


@login_required(login_url="/auth/login/")
def my_picks(request):
    """The user's own Pick of the Day history + personal stats. The leaderboard
    stays general/global; this page is just 'me' — wins/losses, both streaks
    (days picked in a row + wins in a row), and which ones I got right."""
    user = request.user

    # Settlement is lazy — pull any of this user's just-settled results in.
    DailyPick.objects.sync_pending()

    picks = list(
        DailyPick.objects
        .filter(user=user)
        .select_related(
            "potd", "potd__event",
            "potd__event__home_team", "potd__event__away_team",
            "selection", "selection__market", "selection__market__event",
            "selection__market__event__home_team",
            "selection__market__event__away_team",
        )
        .order_by("-potd__date")
    )

    wins = sum(1 for p in picks if p.result == DailyPickResult.WON)
    losses = sum(1 for p in picks if p.result == DailyPickResult.LOST)
    void = sum(1 for p in picks if p.result == DailyPickResult.VOID)
    pending = sum(1 for p in picks if p.result == DailyPickResult.PENDING)
    decided = wins + losses
    win_rate = round(100 * wins / decided) if decided else None

    # chronological (oldest → newest) for streak math
    cur_win_streak, best_win_streak = _win_streaks([p.result for p in reversed(picks)])

    def _team(ev, side):
        t = getattr(ev, side, None) if ev else None
        return getattr(t, "name_medium", None) or "TBD"

    # Filters scope only the table below — the record/streaks above stay lifetime.
    result_filter = request.GET.get("result", "")
    start_date = request.GET.get("start_date", "")
    end_date = request.GET.get("end_date", "")
    _RESULT_BY_KEY = {
        "won": DailyPickResult.WON,
        "lost": DailyPickResult.LOST,
        "pending": DailyPickResult.PENDING,
    }
    visible = picks
    if result_filter in _RESULT_BY_KEY:
        target = _RESULT_BY_KEY[result_filter]
        visible = [p for p in visible if p.result == target]
    if start_date:
        visible = [p for p in visible if p.potd.date.isoformat() >= start_date]
    if end_date:
        visible = [p for p in visible if p.potd.date.isoformat() <= end_date]

    rows = []
    for p in visible:
        label, kind = _RESULT_META.get(p.result, ("—", "muted"))
        rows.append({
            "date": p.potd.date,
            "event_id": p.potd.event_id,
            "home": _team(p.potd.event, "home_team"),
            "away": _team(p.potd.event, "away_team"),
            "pick": humanize_selection(p.selection),
            "result_label": label,
            "result_kind": kind,
        })

    context = {
        "total": len(picks),
        "wins": wins,
        "losses": losses,
        "void": void,
        "pending": pending,
        "win_rate": win_rate,
        "participation_current": user.potd_current_streak,
        "participation_best": user.potd_best_streak,
        "win_current": cur_win_streak,
        "win_best": best_win_streak,
        "rows": rows,
        "result_filter": result_filter,
        "start_date": start_date,
        "end_date": end_date,
        "quick_filters": [
            {"label": "All",     "value": "",        "is_active": not result_filter},
            {"label": "Won",     "value": "won",     "is_active": result_filter == "won"},
            {"label": "Lost",    "value": "lost",    "is_active": result_filter == "lost"},
            {"label": "Pending", "value": "pending", "is_active": result_filter == "pending"},
        ],
    }
    return render(request, "portal/potd/my_picks.html", context)
