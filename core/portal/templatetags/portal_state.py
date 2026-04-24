"""Template tags for mapping raw state strings to badge variants + labels."""
from django import template

register = template.Library()


STATE_MAP = {
    # Tournament / Match
    "created":    {"variant": "info",    "label": "Upcoming"},
    "inprogress": {"variant": "primary", "label": "In Progress"},
    "completed":  {"variant": "success", "label": "Completed"},
    "aborted":    {"variant": "danger",  "label": "Aborted"},
    # Match-specific
    "pending":    {"variant": "muted",   "label": "Pending"},
    "accepted":   {"variant": "success", "label": "Accepted"},
    "declined":   {"variant": "danger",  "label": "Declined"},
    # Invite
    "sent":       {"variant": "muted",   "label": "Invite sent"},
    "expired":    {"variant": "warning", "label": "Expired"},
}


@register.filter
def state_badge(state):
    """Return {variant, label} for a state string; default muted + raw state."""
    if not state:
        return {"variant": "muted", "label": "—"}
    return STATE_MAP.get(state, {"variant": "muted", "label": state.title()})
