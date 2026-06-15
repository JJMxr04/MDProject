"""Developer updates page — beta testing notes and a running changelog of
what's new, changed, or known-broken. Discovered via the sidebar.

Entries live here as plain data (newest first) so adding a note is a one-line
edit: prepend a dict to ``UPDATES``. ``tag`` drives the colored pill — keep it
to one of: "new", "improved", "fixed", "known-issue".
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# Newest first. Dates are ISO strings (rendered as-is). ``items`` are bullets.
UPDATES = [
    {
        "date": "2026-06-09",
        "title": "Welcome to the beta",
        "tag": "new",
        "items": [
            "You're testing an early build — expect rough edges and frequent changes.",
            "This page is where we'll post what's new, what's fixed, and what's still broken.",
            "Found something off? Send it our way from the Support page.",
        ],
    },
]

# Short, friendly label per tag for the pill.
TAG_LABELS = {
    "new": "New",
    "improved": "Improved",
    "fixed": "Fixed",
    "known-issue": "Known issue",
}

# Plain bullets shown under "While we're testing, keep in mind".
KEEP_IN_MIND = [
    "Your data may be reset between test rounds — don't rely on anything being permanent yet.",
    "Some features are visible but not finished; if a button does nothing, it's likely not wired up.",
    "Email notifications can be delayed or skipped while we tune them.",
    "If something looks broken, refresh once before reporting — it's often a stale page.",
    "If neither player enters a tiebreaker and the scores are tied, There if a coin toss up for who wins. We are still tyring to figure out the best way to handle this, so if you have a better idea (Which it probably is), please suggest it.",
    "You may not see all the leagues, games, or markets you would like but we are working with a fixed budget (0$).  As we grow and are able to make revenue we will include a larger selection.",
    "Outcomes are checked hourly."
]

# Status table. ``status`` drives the pill color — keep it to one of:
# "working", "in-progress", "broken", "planned".
FEATURE_STATUS = [
    {"feature": "Single PVP Bets", "working": "planned", "notes": "Challenge your opponent to a single outcome"},
    {"feature": "Matches", "status": "working", "notes": "Create, play, and score matches."},
    {"feature": "Tournaments", "status": "in-progress", "notes": "Bracket generation still being refined."},
    {"feature": "Analytics", "status": "in-progress", "notes": "Coming in a later beta round."},
]

STATUS_LABELS = {
    "working": "Working",
    "in-progress": "In progress",
    "broken": "Broken",
    "planned": "Planned",
}


@login_required(login_url="/auth/login/")
def developer_updates_view(request):
    updates = [{**u, "tag_label": TAG_LABELS.get(u["tag"], u["tag"])} for u in UPDATES]
    feature_status = [
        {**row, "status_label": STATUS_LABELS.get(row["status"], row["status"])}
        for row in FEATURE_STATUS
    ]
    return render(request, "portal/developer_updates/developer_updates.html", {
        "updates": updates,
        "keep_in_mind": KEEP_IN_MIND,
        "feature_status": feature_status,
    })
