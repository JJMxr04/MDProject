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
from django.contrib.auth import get_user_model
# from core.user.models import User
User = get_user_model()
from core.blog.writer.models import SubscriptionPlan

import stripe
from django.conf import settings
from django.shortcuts import redirect, render
from django.http import JsonResponse

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
        return render(request, path)
    except Exception as e:
        print(e)
        # In case of any errors, redirect to the dashboard as a fallback
        return render(request, 'portal/payments/error.html')



@login_required(login_url='/auth/login/')
def create_checkout_session(request, creator_id):
    # Retrieve the creator's Stripe account ID
    creator = User.objects.get(public_id=creator_id)
    subscription_plan = SubscriptionPlan.objects.get(writer=creator)

    if not creator.stripe_account_id:
        return JsonResponse({'error': 'Creator does not have a connected Stripe account'}, status=400)

    try:
        # Create a Checkout session for destination charges
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Subscription Payment to {creator.first_name} {creator.last_name}',
                        'description': 'Payment for creator content',
                    },
                    'unit_amount': int(int(subscription_plan.price) * 100),  # Amount in cents (e.g., $10.00)
                },  # Added missing comma here
                'quantity': 1,
            }],
            payment_intent_data={
                'application_fee_amount': int(int(subscription_plan.price) * 100 * (int(settings.PLATFORM_COST) / 100)),  # Platform fee in cents (e.g., $2.00)
                'transfer_data': {
                    'destination': creator.stripe_account_id,  # Creator's Stripe account ID
                },
            },
            mode='payment',
            success_url=request.build_absolute_uri('/success/'),
            cancel_url=request.build_absolute_uri('/cancel/'),
        )
        return JsonResponse({'id': checkout_session.id})
    except Exception as e:
        print(e)
        return JsonResponse({'error': str(e)}, status=500)


def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError as e:
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        # Fulfill the purchase, e.g., mark subscription as active
        handle_checkout_session(session)

    return JsonResponse({'status': 'success'}, status=200)