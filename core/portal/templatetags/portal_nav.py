"""Navigation template tags — active-state-aware sidenav items."""
from django import template
from django.urls import NoReverseMatch, reverse

from core.billing.entitlement import user_can_access_analytics

register = template.Library()


@register.filter(name="can_access_analytics")
def can_access_analytics(user) -> bool:
    """Template-side hook into the entitlement helper. Use in the sidebar
    so the analytics row honors the kill-switch + missing-Subscription
    cases without poking at ``user.subscription`` directly (that path
    raises ``Subscription.DoesNotExist`` when no row exists)."""
    return user_can_access_analytics(user)


@register.inclusion_tag("portal/components/_sidenav_item.html", takes_context=True)
def sidenav_item(context, url, icon, label, prefix=None, badge=None, exact=False):
    """Render a single sidebar nav item. Active when the current request
    path starts with `prefix` (or the resolved `url` if no prefix given).
    Set ``exact=True`` to require an exact path match instead of a prefix
    match — used by children whose parent route is also their prefix
    (e.g. the Explore child under Analytics, where the parent sits on
    ``/web/portal/analytics/`` and would otherwise mark Explore active
    on every deeper analytics page).
    ``prefix`` may be a single string or a list/tuple of strings — the
    item highlights when the current path starts with any of them. Used
    by the Settings row, which is the parent of both /web/portal/user/
    profile/ and /web/portal/billing/.
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
        if isinstance(prefix, (list, tuple)):
            match_prefixes = list(prefix)
        elif isinstance(prefix, str) and "," in prefix:
            # Convenience for templates that can't pass a list literal —
            # comma-separated string is split and trimmed.
            match_prefixes = [p.strip() for p in prefix.split(",") if p.strip()]
        else:
            match_prefixes = [prefix or href]
        is_active = any(
            bool(p) and current_path.startswith(p) for p in match_prefixes
        )

    return {
        "href": href,
        "icon": icon,
        "label": label,
        "is_active": is_active,
        "badge": badge,
    }
