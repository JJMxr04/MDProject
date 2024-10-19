from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.blog.writer.decorator import writer_required
from core.event.models import Event, Sport  # Adjust import according to your project's structure
from django.utils.dateparse import parse_date
from core.event.serializers.event import EventSerializer
import json
from uuid import UUID
from django.core.serializers.json import DjangoJSONEncoder
import stripe
import os
import json
from django.conf import settings

stripe.api_key = settings.STRIPE_API_KEY
stripe.api_version = '2023-10-16'


@login_required(login_url='/auth/login/')
@writer_required
def writer_dashboard(request):
    user = request.user

    # Assuming the user model has a field for Stripe account ID
    stripe_account_id = user.stripe_account_id

    if not stripe_account_id:
        # No connected account, redirect to onboarding
        return redirect('core-portal:onboarding')  # Replace 'onboarding_page' with your actual onboarding URL name

    # Fetch the account details from Stripe
    try:
        account = stripe.Account.retrieve(stripe_account_id)
    except stripe.error.StripeError:
        # Handle any potential error here (e.g., log the error)
        return redirect('core-portal:onboarding') 

    # Check if the account is fully set up
    if account['charges_enabled'] and account['details_submitted']:
        # Account is fully set up, display the dashboard
         return render(request,'portal/blog/writer/writer-dashboard.html')
    else:
        # Account is not fully set up, redirect to onboarding
        return redirect('core-portal:onboarding') 