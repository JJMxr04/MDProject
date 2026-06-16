from django import template

from core.portal import cards

register = template.Library()


@register.filter
def event_fixture(ev):
    """Template bridge: aggregator event dict -> normalized card fixture."""
    return cards.fixture_from_dict(ev)
