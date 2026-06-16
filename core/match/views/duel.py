"""Duel challenge UI + send endpoint (phase 14).

- ``duels_page_view`` renders the duel hub: a "Create duel" modal (the
  duel-builder island), incoming challenges to accept/decline, and the user's
  in-progress + finished duels with a W/L/D record. The three lists page
  independently (``cpage`` / ``apage`` / ``fpage``); read helpers live in
  ``core.match.duels``.
- ``duel_events_view`` returns the upcoming-events catalog the island browses.
- ``send_duel_view`` is the JSON write: ``event_id`` + ``selection_id`` (the side
  the challenger takes) + ``opponent_id`` (a friend's public_id). Per-event
  markets are loaded by the island from the existing ``event_outcomes`` endpoint;
  validation and the invite write live in ``core.match.duels``.
"""

from __future__ import annotations

import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from core.match import duels
from core.user.models import User

# How far ahead the duel event picker looks.
DUEL_LOOKAHEAD = timedelta(days=14)
DUEL_EVENTS_TTL = 30  # seconds

# Each of the three duel-page lists pages independently at this size.
DUEL_PAGE_SIZE = 10


@login_required(login_url="/auth/login/")
def duels_page_view(request):
    user = request.user
    challenges = Paginator(
        duels.incoming_duel_invites(user), DUEL_PAGE_SIZE,
    ).get_page(request.GET.get("cpage"))
    sent = Paginator(
        duels.outgoing_duel_invites(user), DUEL_PAGE_SIZE,
    ).get_page(request.GET.get("spage"))
    accepted = Paginator(
        duels.accepted_duels(user), DUEL_PAGE_SIZE,
    ).get_page(request.GET.get("apage"))
    finished = Paginator(
        duels.finished_duels(user), DUEL_PAGE_SIZE,
    ).get_page(request.GET.get("fpage"))

    # Scout the challenger before accepting (phase 9). PRO gets a card per
    # incoming challenge; FREE gets one upsell for the section (not one per
    # row) + a single paywall_viewed signal.
    from core.billing.entitlement import user_can_access_analytics
    scouting_entitled = user_can_access_analytics(user)
    if scouting_entitled:
        from core.match import scouting as scouting_mod
        for inv in challenges:
            try:
                inv.scouting = scouting_mod.scout_user(inv.sender)
            except Exception:
                inv.scouting = None
    elif challenges.object_list:
        from core.metrics.models import track
        track(user, "paywall_viewed",
              feature="opponent_scouting", context="duel_challenge")

    from core.ranking.standings import global_leaderboard
    leaderboard = global_leaderboard(limit=5)

    # Pager links for one list must preserve the other lists' page positions,
    # so each carries the siblings' current page numbers.
    c, s, a, f = challenges.number, sent.number, accepted.number, finished.number
    context = {
        "scouting_entitled": scouting_entitled,
        "leaderboard": leaderboard,
        "duel_record": duels.duel_record(user),
        "challenges": challenges,
        "sent": sent,
        "accepted": accepted,
        "finished": finished,
        "accepted_rows": [duels.duel_row(m, user) for m in accepted],
        "finished_rows": [duels.duel_row(m, user) for m in finished],
        "challenges_other_qs": f"spage={s}&apage={a}&fpage={f}",
        "sent_other_qs": f"cpage={c}&apage={a}&fpage={f}",
        "accepted_other_qs": f"cpage={c}&spage={s}&fpage={f}",
        "finished_other_qs": f"cpage={c}&spage={s}&apage={a}",
    }
    return render(request, "portal/match/duels.html", context)


@require_GET
@login_required(login_url="/auth/login/")
def duel_events_view(request):
    """Upcoming events the challenger can duel on. Not match-scoped (unlike
    ``available_events_for_match``) — the duel picker is standalone."""
    cache_key = "portal:duel:events"
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse({"items": cached})

    from core.event.providers.aggregator_client import AggrigatorClient, AggrigatorError

    now = timezone.now()
    try:
        body = AggrigatorClient().list_events(
            starts_after=now.isoformat(),
            starts_before=(now + DUEL_LOOKAHEAD).isoformat(),
            page_size=100,
        )
    except AggrigatorError:
        return JsonResponse({"items": []})

    items = []
    for it in (body.get("items") or []):
        home = (it.get("home_team") or {}).get("name") or ""
        away = (it.get("away_team") or {}).get("name") or ""
        items.append({
            "event_id": it.get("id"),
            "label": f"{away} @ {home}" if (home and away) else (it.get("id") or ""),
            "league": (it.get("league") or {}).get("name") or "",
            "start_time": it.get("start_time"),
        })
    cache.set(cache_key, items, timeout=DUEL_EVENTS_TTL)
    return JsonResponse({"items": items})


@require_POST
@login_required(login_url="/auth/login/")
def send_duel_view(request):
    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        body = request.POST

    event_id = (body.get("event_id") or "").strip()
    selection_id = (body.get("selection_id") or "").strip()
    opponent_id = (body.get("opponent_id") or "").strip()
    if not (event_id and selection_id and opponent_id):
        return JsonResponse(
            {"detail": "event_id, selection_id and opponent_id are required."},
            status=400,
        )

    opponent = User.objects.filter(public_id=opponent_id).first() or \
        User.objects.filter(pk=opponent_id).first()
    if opponent is None:
        return JsonResponse({"detail": "We couldn't find that player."}, status=404)

    try:
        invite = duels.send_duel(request.user, opponent, event_id, selection_id)
    except duels.DuelError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

    return JsonResponse({"ok": True, "invite_id": str(invite.pk)}, status=201)
