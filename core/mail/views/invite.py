# views.py
from django.shortcuts import render, redirect
from core.mail.forms import InviteForm
from django.utils import timezone


def create_invite(request):
    print(request.body)
    if request.method == 'POST':
        form = InviteForm(request.POST)
        if form.is_valid():
            invite = form.save(commit=False)
            invite.sender = request.user  # Automatically set the sender to the current user
            invite.invited_date = timezone.now()  # Set the invited date to now
            invite.save()
            return redirect('core-portal:invite_success')  # Redirect to a success page or wherever you want
    else:
        form = InviteForm()

    return redirect('core-portal:portal-public-match-list')
