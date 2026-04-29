"""Template tag: render a Selection in plain English.

Usage:
    {% load humanize_pick %}
    {{ bet.owner_outcome|humanize_pick }}
        → "Detroit Red Wings to win"

Wraps ``core.event.odds.humanize.humanize_selection`` — single source of
truth so the JS popup and server-rendered pages stay in sync.
"""

from __future__ import annotations

from django import template

from core.event.odds.humanize import humanize_payload, humanize_selection

register = template.Library()


@register.filter(name="humanize_pick")
def humanize_pick_filter(selection):
    """Filter for Selection model rows: ``{{ selection|humanize_pick }}``."""
    return humanize_selection(selection)


@register.simple_tag(name="humanize_pick_payload")
def humanize_pick_payload(event, market, selection):
    """Tag for raw aggregator dicts (upcoming-event detail page):
        {% humanize_pick_payload event market sel %}
    """
    return humanize_payload(event, market, selection)
