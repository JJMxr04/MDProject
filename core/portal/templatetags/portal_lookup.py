"""Tiny dict / list helpers for templates.

Django templates can't index dicts by a variable key directly
(``{{ d[key] }}`` is invalid). This filter unblocks that for a few places
where the alternative is awkward {% with %} chains.
"""

from django import template

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
