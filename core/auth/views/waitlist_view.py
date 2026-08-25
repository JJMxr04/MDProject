from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from core.auth.forms import WaitListForm
from core.auth.models.waitlist import WaitlistEntry
from core.ratelimit import rate_limit


class WaitListView(View):
    form_class = WaitListForm
    template_name = 'authorization/waitlist.html'
    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    # Anonymous endpoint that sends an email per submission — brake it.
    @method_decorator(rate_limit("auth-waitlist", 5, 3600))
    def post(self, request):
        form = WaitListForm(request.POST)
        # An email that's already on the list gets the same thank-you
        # redirect as a fresh signup. The unique=True form error would
        # otherwise confirm list membership to anyone (enumeration), and
        # short-circuiting also avoids re-sending the thank-you email.
        email_value = (request.POST.get('email') or '').strip()
        if email_value and WaitlistEntry.objects.filter(email__iexact=email_value).exists():
            return redirect('/auth/waitlist/thank-you/')
        if form.is_valid():
            form.save()
            return redirect('/auth/waitlist/thank-you/')
        return render(request, self.template_name, {'form': form})

def WaitlistThankYouView(request):

        return render(request, 'authorization/waitlist_thank_you.html', {'title': 'Thank You'})

