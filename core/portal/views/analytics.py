"""Portal analytics views — render the betting-decision dashboard.

Three top-level pages:
- ``tonight`` — list of events kicking off in the next 24h with denormalized
  ML/spread/total. Click a row to drill in.
- ``tonight_detail`` — single-event panel: implied probabilities, vig,
  best price per book.
- ``edge`` — power-user view of biggest current cross-book disagreements.

Every view degrades gracefully if the aggrigator is unreachable — the
client returns empty shapes and the templates show empty-state cards.
"""

from __future__ import annotations

from django.shortcuts import render

from core.billing.decorators import require_paid
from core.portal.services import aggrigator_client


@require_paid
def analytics_tonight(request):
    sport = request.GET.get("sport") or None
    league = request.GET.get("league") or None
    events = aggrigator_client.events_today(
        sport=sport, league=league, hours_ahead=24,
        tenant_key=request.user.aggrigator_api_key or None,
    )
    ctx = {
        "events": events,
        "filter_sport": sport or "",
        "filter_league": league or "",
        "active_tab": "tonight",
    }
    return render(request, "portal/analytics/tonight.html", ctx)


@require_paid
def analytics_tonight_detail(request, event_id: str):
    key = request.user.aggrigator_api_key or None
    event = aggrigator_client.event_detail(event_id)  # public — no key
    probabilities = aggrigator_client.event_probabilities(event_id, tenant_key=key)
    best_prices = aggrigator_client.event_best_prices(event_id, tenant_key=key)
    ctx = {
        "event": event,
        "event_id": event_id,
        "probabilities": probabilities,
        "best_prices": best_prices,
        "active_tab": "tonight",
    }
    return render(request, "portal/analytics/tonight_detail.html", ctx)


@require_paid
def analytics_edge(request):
    try:
        threshold_pct = float(request.GET.get("threshold_pct") or 2.0)
    except ValueError:
        threshold_pct = 2.0
    payload = aggrigator_client.disagreements(
        threshold_pct=threshold_pct, hours_ahead=24, limit=25,
        tenant_key=request.user.aggrigator_api_key or None,
    )
    ctx = {
        "rows": payload.get("rows", []),
        "threshold_pct": payload.get("threshold_pct", threshold_pct),
        "active_tab": "edge",
    }
    return render(request, "portal/analytics/edge.html", ctx)
