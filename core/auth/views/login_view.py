from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.utils import timezone

from core.auth import twofa
from core.auth.views.twofa import SESSION_PENDING_KEY


class LoginView(LoginView):  # Renamed class to avoid potential conflicts with the built-in LoginView
    template_name = 'authorization/login.html'

    def dispatch(self, request, *args, **kwargs):
        # Redirect logged-in users to the appropriate dashboard
        if request.user.is_authenticated:
            if request.user.is_staff:
                return redirect(reverse_lazy('core-admin:admin_dashboard'))
            return redirect(reverse_lazy('core-portal:portal-dashboard'))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Credentials are correct. If this user enrolled in 2FA, DON'T log them
        # in yet — stash the pending identity server-side (5-min TTL, checked in
        # the verify view) and send them to the second step. Users without a
        # confirmed device fall through to the normal session login.
        user = form.get_user()
        if twofa.has_2fa(user):
            self.request.session[SESSION_PENDING_KEY] = {
                "user_pk": str(user.pk),
                "ts": timezone.now().isoformat(),
                "next": self.get_redirect_url() or None,  # validated ?next, if any
                # Multiple backends are configured (axes + model); auth_login at
                # the verify step needs to know which one vouched for this user.
                "backend": getattr(user, "backend", None),
            }
            return redirect('core-auth:2fa-verify')
        return super().form_valid(form)

    def get_success_url(self):
        user = self.request.user
        if user.is_staff:
            return reverse_lazy('core-admin:admin_dashboard')
        return reverse_lazy('core-portal:portal-dashboard')  # Ensure this matches the correct URL name in your portal app
