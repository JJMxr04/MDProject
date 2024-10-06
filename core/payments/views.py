from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.shortcuts import render, redirect  # Import redirect
import stripe
import os
from django.contrib.auth.decorators import login_required
from core.blog.writer.decorator import writer_required
from django.shortcuts import render, redirect
from django.urls import reverse  # Import reverse

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
    print('create-link')
    if request.method == 'POST':
        try:
            data = request.json()  # Get the JSON data from the request
            connected_account_id = data.get('account')

            # Generate dynamic return and refresh URLs
            return_url = request.build_absolute_uri(reverse('core-portal:payment_return', args=[connected_account_id]))
            refresh_url = request.build_absolute_uri(reverse('core-portal:payment_refresh', args=[connected_account_id]))

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
    print('create')
    if request.method == 'POST':
        try:
            account = stripe.Account.create()
            user = request.user
            user.stripe_account_id=account.id
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

