from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy

class LoginView(LoginView):  # Renamed class to avoid potential conflicts with the built-in LoginView
    template_name = 'authorization/login.html'

    def get_success_url(self):
        user = self.request.user
        if user.is_staff:
            return reverse_lazy('core-admin:admin-dashboard')  # Use the correct namespace and URL name
        else:
            return reverse_lazy('core-portal:portal-dashboard')  # Ensure this matches the correct URL name in your portal app

        return settings.LOGIN_REDIRECT_URL

