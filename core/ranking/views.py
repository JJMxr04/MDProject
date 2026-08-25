"""Leaderboard pages — season + global, server-rendered."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.ranking import standings
from core.ranking.models import Season


@login_required(login_url="/auth/login/")
def leaderboard_view(request):
    scope = request.GET.get("scope", "season")

    # Season selector: ACTIVE first, then CLOSED (most recent). Default to the
    # one named in ?season=, else the active season, else the latest closed.
    seasons = list(
        Season.objects.exclude(status=Season.Status.DRAFT).order_by("-start_date")
    )
    chosen = None
    slug = request.GET.get("season")
    if slug:
        chosen = next((s for s in seasons if s.slug == slug), None)
    if chosen is None:
        chosen = Season.active() or (seasons[0] if seasons else None)

    division = request.GET.get("division")
    division = int(division) if (division and division.isdigit()) else None

    context = {
        "scope": scope,
        "seasons": seasons,
        "chosen_season": chosen,
        "divisions": standings.season_divisions(chosen) if chosen else [],
        "active_division": division,
        "season_rows": standings.season_leaderboard(chosen, division) if chosen else [],
        "global_rows": standings.global_leaderboard(),
    }
    return render(request, "portal/ranking/leaderboard.html", context)
