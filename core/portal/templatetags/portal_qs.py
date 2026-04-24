"""Querystring template tags — preserve GET params across page links."""
from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring_without_page(context):
    """Return the current GET querystring minus the `page` parameter."""
    request = context.get("request")
    if not request:
        return ""
    qd = request.GET.copy()
    qd.pop("page", None)
    return qd.urlencode()
