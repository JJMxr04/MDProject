import logging

from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views import View
from core.auth.forms.register_form import RegisterForm
from django.contrib.auth import login
from django.contrib import messages
from core.auth.models import email  # Import your email sending function
from core.ratelimit import rate_limit

logger = logging.getLogger(__name__)

# Session keys for the invite/referral hand-off between GET (?invite= /
# ?ref=) and the POST that creates the account (plan Phase 4 §3).
PENDING_INVITE_SESSION_KEY = 'pending_invite_token'
REFERRAL_SESSION_KEY = 'referral_friend_code'


class RegisterView(View):
    form_class = RegisterForm
    template_name = 'signup/signup.html'

    def get(self, request):
        form = self.form_class()
        # Email-token invite (Phase 4 §3): stash the token for the POST and
        # prefill the email so the waitlist bypass keys on the right address.
        token = request.GET.get('invite')
        if token:
            from core.mail.models import PendingInvite
            pending = PendingInvite.objects.resolve_token(token)
            if pending is not None:
                request.session[PENDING_INVITE_SESSION_KEY] = token
                form = self.form_class(initial={'email': pending.email})
                messages.info(
                    request,
                    f'{pending.inviter.username} invited you — sign up with '
                    f'{pending.email} and you\'ll be friends automatically.',
                )
            else:
                messages.warning(
                    request,
                    'That invite link is no longer valid — ask your friend '
                    'to send a new one.',
                )
        # Referral link (tokenless variant): friend edge on signup, no
        # waitlist bypass.
        ref = request.GET.get('ref')
        if ref:
            request.session[REFERRAL_SESSION_KEY] = ref
        return render(request, self.template_name, {'form': form})

    # Anonymous, sends an activation email, and the waitlist-approval form
    # error makes approval status probeable — brake it (plan §7.5 item 3).
    @method_decorator(rate_limit("auth-register", 5, 3600))
    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            user = form.save()
            self._apply_invites_and_referral(request, user)
            email.send_activation_email(user,request)
            messages.success(request, 'Registration successful! You are now logged in.')
            return redirect('core-auth:activation-email')  # Replace 'home' with the name of your home page URL pattern
        else:
            messages.error(request, 'Registration failed. Please correct the errors below.')
            for field, errors in form.errors.items():
                for error in errors:
                    messages.warning(request, f"{field.capitalize()}: {error}")
        return render(request, self.template_name, {'form': form})

    @staticmethod
    def _apply_invites_and_referral(request, user):
        """Consume pending invites for this email (friend edge + the
        materialized match invite) and apply a referral friend edge.
        Best-effort — a failure here must never break the signup."""
        try:
            from core.mail.models import PendingInvite
            request.session.pop(PENDING_INVITE_SESSION_KEY, None)
            PendingInvite.objects.consume_for_user(user)

            ref = request.session.pop(REFERRAL_SESSION_KEY, None)
            if ref:
                from core.user.models import User
                referrer = User.find_by_friend_code(ref)
                if referrer is not None and referrer.pk != user.pk:
                    referrer.add_friend(user)
                    from core.metrics.models import track
                    track(user, "referral_signup", referrer_id=str(referrer.pk))
        except Exception:
            logger.exception("post-signup invite/referral application failed")
