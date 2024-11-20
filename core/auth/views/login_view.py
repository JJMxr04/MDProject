from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.shortcuts import redirect

class LoginView(LoginView):  # Renamed class to avoid potential conflicts with the built-in LoginView
    template_name = 'authorization/login.html'

    def dispatch(self, request, *args, **kwargs):
        # Redirect logged-in users to the appropriate dashboard
        if request.user.is_authenticated:
            if request.user.is_staff:
                return redirect(reverse_lazy('core-admin:admin_dashboard'))
            return redirect(reverse_lazy('core-portal:portal-dashboard'))
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        user = self.request.user
        if user.is_staff:
            return reverse_lazy('core-admin:admin_dashboard')
        return reverse_lazy('core-portal:portal-dashboard')  # Ensure this matches the correct URL name in your portal app
