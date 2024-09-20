from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.edit import UpdateView
from core.user.forms import UserProfileForm

class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'portal/user/user_profile_form.html'
    success_url = reverse_lazy('core-portal:profile')

    def get_object(self, queryset=None):
        # We override get_object to return the currently logged-in user
        return self.request.user
