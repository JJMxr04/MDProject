"""Game-rules page — moved from ``core/web`` (public) to here (portal /
auth-gated). Discovered via the sidebar; old public link redirects here."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required(login_url="/auth/login/")
def rules_view(request):
    return render(request, "portal/rules/rules.html")
