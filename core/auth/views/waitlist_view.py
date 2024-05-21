from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from core.auth.models.waitlist import WaitlistEntry
from core.auth.forms import WaitListForm

class WaitListView(View):
    form_class = WaitListForm
    template_name = 'authorization/waitlist.html'
    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = WaitListForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('/auth/waitlist/thank-you/')
        return render(request, self.template_name, {'form': form})

def WaitlistThankYouView(request):

        return render(request, 'authorization/waitlist_thank_you.html', {'title': 'Thank You'})

