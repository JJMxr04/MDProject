"""Unsubscribe endpoint for engagement emails (plan §7.5 item 4).

Token-authenticated (signed ``public_id``, see core.mail.unsubscribe), so it
works logged-out straight from an email footer. CSRF-exempt because RFC 8058
one-click unsubscribes are POSTed by the recipient's mail provider, which
cannot carry a CSRF token — the signed token is the authorization.
"""

from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from core.mail.unsubscribe import read_token
from core.ratelimit import rate_limit
from core.user.models import User


@csrf_exempt
@rate_limit("unsubscribe", 30, 3600)
def unsubscribe_view(request, token):
    public_id = read_token(token)
    user = User.objects.filter(public_id=public_id).first() if public_id else None

    if user is None:
        # Bad/garbled token — generic page, no signal about validity.
        return render(
            request, "authorization/unsubscribe.html",
            {"state": "invalid"}, status=404,
        )

    if request.method == "POST" and request.POST.get("action") == "resubscribe":
        user.email_notifications = True
        user.save(update_fields=["email_notifications"])
        return render(
            request, "authorization/unsubscribe.html",
            {"state": "resubscribed", "token": token},
        )

    # GET from the footer link or one-click POST from a mail provider.
    user.email_notifications = False
    user.save(update_fields=["email_notifications"])
    return render(
        request, "authorization/unsubscribe.html",
        {"state": "unsubscribed", "token": token},
    )
