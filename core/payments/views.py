from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.shortcuts import render, redirect  # Import redirect
import stripe
import os
from django.contrib.auth.decorators import login_required
from core.blog.writer.decorator import writer_required
from django.shortcuts import render, redirect


# Set up the Stripe API key
stripe.api_key = settings.STRIPE_API_KEY
stripe.api_version = '2023-10-16'

@login_required(login_url='/auth/login/')
@writer_required
def onboarding_page(request):
    print('onboarding')
    return render(request, 'portal/payments/onboarding.html')

# Create an account link for onboarding
@login_required(login_url='/auth/login/')
@writer_required
def create_account_link(request):
    if request.method == 'POST':
        try:
            data = request.json()  # Get the JSON data from the request
            connected_account_id = data.get('account')

            account_link = stripe.AccountLink.create(
                account=connected_account_id,
                return_url=f"http://localhost:4242/return/{connected_account_id}",
                refresh_url=f"http://localhost:4242/refresh/{connected_account_id}",
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
            account = stripe.Account.create()
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
        return render(request, 'portal/payments/onboarding.html')
    except Exception as e:
        # In case of any errors, redirect to the dashboard as a fallback
        return redirect('core-portal:portal-dashboard')

