"""Support page — how to reach us by email for support requests, bug
reports, and feature ideas. Discovered via the sidebar."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

SUPPORT_EMAIL = "paradisesportsmande+support@gmail.com"
FEATURES_EMAIL = "paradisesportsmande+newfeatures@gmail.com"


@login_required(login_url="/auth/login/")
def support_view(request):
    return render(request, "portal/support/support.html", {
        "support_email": SUPPORT_EMAIL,
        "features_email": FEATURES_EMAIL,
    })
