"""Navigation template tags — active-state-aware sidenav items."""
from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()


@register.inclusion_tag("portal/components/_sidenav_item.html", takes_context=True)
def sidenav_item(context, url, icon, label, prefix=None, badge=None, exact=False):
    """Render a single sidebar nav item. Active when the current request
    path starts with `prefix` (or the resolved `url` if no prefix given).
    Set ``exact=True`` to require an exact path match instead of a prefix
    match — used by children whose parent route is also their prefix
    (e.g. the Explore child under Analytics, where the parent sits on
    ``/web/portal/analytics/`` and would otherwise mark Explore active
    on every deeper analytics page).
    Optional ``badge`` renders a small label after the item text — used
    by the analytics row to flag PRO-gated features for FREE users.
    """
    try:
        href = reverse(url)
    except NoReverseMatch:
        href = "#"

    request = context.get("request")
    current_path = request.path if request else ""
    if exact:
        is_active = bool(href) and current_path == href
    else:
        match_prefix = prefix or href
        is_active = bool(match_prefix) and current_path.startswith(match_prefix)

    return {
        "href": href,
        "icon": icon,
        "label": label,
        "is_active": is_active,
        "badge": badge,
    }
