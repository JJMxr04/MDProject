"""Tiny dict / list helpers for templates.

Django templates can't index dicts by a variable key directly
(``{{ d[key] }}`` is invalid). This filter unblocks that for a few places
where the alternative is awkward {% with %} chains.
"""

from django import template
from django.utils.dateparse import parse_datetime

register = template.Library()


@register.filter(name="get_item")
def get_item(mapping, key):
    """``{{ leagues_by_sport|get_item:sport.id }}`` → list."""
    if mapping is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        # Not a dict — fall back to indexing for lists/tuples.
        try:
            return mapping[key]
        except (TypeError, KeyError, IndexError):
            return None


@register.filter(name="to_dt")
def to_dt(value):
    """Parse an ISO-8601 string into a datetime so ``|date`` can format it.

    Analytics payloads come back from the aggrigator as JSON; datetimes
    are serialized to ISO strings by FastAPI, but Django's ``|date``
    filter only accepts datetime objects. Pipe through ``|to_dt`` first."""
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return parse_datetime(value)
    return value
