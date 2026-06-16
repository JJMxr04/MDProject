import hashlib

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic.edit import UpdateView
from core.user.forms import UserProfileForm
from core.user.models import User, UserAvatar  # custom user (app label core_user), not django.contrib.auth.User

class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'portal/user/user_profile_form.html'
    success_url = reverse_lazy('core-portal:profile')

    def get_object(self, queryset=None):
        # We override get_object to return the currently logged-in user
        return self.request.user

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from core.ranking.models import PlayerProgress
        ctx["progress"] = PlayerProgress.objects.filter(user=self.request.user).first()
        ctx["badges"] = (
            self.request.user.badges.select_related("season").order_by("-earned_at")
        )
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        avatar_bytes = form.cleaned_data.get('avatar_upload')
        if avatar_bytes:
            etag = hashlib.sha256(avatar_bytes).hexdigest()[:32]
            UserAvatar.objects.update_or_create(
                user=self.request.user,
                defaults={
                    "image": avatar_bytes,
                    "content_type": "image/webp",
                    "byte_size": len(avatar_bytes),
                    "etag": etag,
                    "status": "ok",
                    "source": "upload",
                },
            )
        return response
