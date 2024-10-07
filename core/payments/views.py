from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.shortcuts import render, redirect  # Import redirect
import stripe
import os
from django.contrib.auth.decorators import login_required
from core.blog.writer.decorator import writer_required
from django.shortcuts import render, redirect
from django.urls import reverse  # Import reverse
import json

# Set up the Stripe API key
stripe.api_key = settings.STRIPE_API_KEY
stripe.api_version = '2023-10-16'

@login_required(login_url='/auth/login/')
def onboarding_page(request):
    # Check if the user already has a Stripe account
    print(request.user.stripe_account_id)
    if request.user.stripe_account_id:
        return redirect('core-portal:writer-subscription-plan')

    return render(request, 'portal/payments/onboarding.html')

# Create an account link for onboarding
@login_required(login_url='/auth/login/')
@writer_required
def create_account_link(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)  # Parse JSON data from the request body
            connected_account_id = data.get('account')
            print('create-link-3')
            # Ensure connected_account_id is valid and not None
            if connected_account_id is None:
                return JsonResponse({'error': 'Connected account ID is required.'}, status=400)

            # Generate dynamic return and refresh URLs
            # return_url = request.build_absolute_uri(reverse('core-portal:payment_return', args=[connected_account_id]))
            # print(return_url)
            # refresh_url = request.build_absolute_uri(reverse('core-portal:payment_refresh', args=[connected_account_id]))
            return_url = f"http://localhost:8000/web/portal/payments/return/{connected_account_id}/"
            refresh_url = f"http://localhost:8000/web/portal/payments/return/{connected_account_id}/"
            account_link = stripe.AccountLink.create(
                account=connected_account_id,
                return_url=return_url,
                refresh_url=refresh_url,
                type="account_onboarding",
            )

            return JsonResponse({'url': account_link.url})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# Create a new Stripe account
@login_required(login_url='/auth/login/')
@writer_required
def create_account(request):
    if request.method == 'POST':
        try:
            user = request.user
            # Check if the user already has a Stripe account
            if user.stripe_account_id:
                return JsonResponse({'error': 'User already has a Stripe account.'}, status=400)

            account = stripe.Account.create()
            user.stripe_account_id = account.id
            user.save()
            return JsonResponse({'account': account.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


# # Serve static files or fallback to the frontend

@login_required(login_url='/auth/login/')
@writer_required
def catch_all(request, connected_account_id=None, path=None):
    try:
        # If the path is provided, you could handle specific routing logic here
        # For now, let's assume any unmatched route renders your default template
        return redirect('core-portal:onboarding')
    except Exception as e:
        print('help')
        print(e)
        # In case of any errors, redirect to the dashboard as a fallback
        return redirect('core-portal:portal-dashboard')

