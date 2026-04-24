"""Navigation template tags — active-state-aware sidenav items."""
from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()


@register.inclusion_tag("portal/components/_sidenav_item.html", takes_context=True)
def sidenav_item(context, url, icon, label, prefix=None):
    """Render a single sidebar nav item. Active when the current request
    path starts with `prefix` (or the resolved `url` if no prefix given).
    """
    try:
        href = reverse(url)
    except NoReverseMatch:
        href = "#"

    request = context.get("request")
    current_path = request.path if request else ""
    match_prefix = prefix or href
    is_active = bool(match_prefix) and current_path.startswith(match_prefix)

    return {
        "href": href,
        "icon": icon,
        "label": label,
        "is_active": is_active,
    }
