"""``{% load usertime %}`` — render a datetime in the viewing user's timezone
and clock format.

The timezone is applied by TimezonePreferenceMiddleware (web) or
core.timeprefs.user_time_context (email); this filter only picks the clock
format. It is the single rendering point for user-facing times in templates, so
the 12h/24h choice lives in exactly one place (core.timeprefs.format_datetime,
shared with serializers that ship pre-formatted *_display strings to JS).

    {{ event.start_time|usertime }}            → "Jun 22, 2026 7:00 PM" / "… 19:00"
    {{ event.start_time|usertime:"time" }}     → "7:00 PM" / "19:00"
    {{ ev.created_at|usertime:"date" }}        → "Jun 22, 2026"
"""
from django import template

from core import timeprefs

register = template.Library()


@register.filter
def usertime(value, style="datetime"):
    return timeprefs.format_datetime(value, style)
