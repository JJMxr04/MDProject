from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.shortcuts import render, redirect
from django.urls import reverse
import stripe
import os
import json
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from core.blog.writer.decorator import writer_required
from core.blog.writer.models import SubscriptionPlan
from core.blog.client.models import Subscription
from django.contrib.auth import get_user_model
from dateutil.relativedelta import relativedelta
from django.views.decorators.csrf import csrf_exempt


User = get_user_model()

# Set up the Stripe API key
stripe.api_key = settings.STRIPE_API_KEY
stripe.api_version = '2023-10-16'


@login_required(login_url='/auth/login/')
def onboarding_page(request):
    if request.user.stripe_account_id:
        return redirect('core-portal:writer-subscription-plan')
    return render(request, 'portal/payments/onboarding.html')


# @login_required(login_url='/auth/login/')
def successful_payment(request):
    return render(request, 'portal/payments/success.html')


@login_required(login_url='/auth/login/')
@writer_required
def create_account_link(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            connected_account_id = data.get('account')
            if connected_account_id is None:
                return JsonResponse({'error': 'Connected account ID is required.'}, status=400)

            return_url = f"https://paradise-sports-94ea4023d1fa.herokuapp.com/web/portal/payments/return/{connected_account_id}/"
            refresh_url = f"https://paradise-sports-94ea4023d1fa.herokuapp.com/web/portal/payments/return/{connected_account_id}/"

            account_link = stripe.AccountLink.create(
                account=connected_account_id,
                return_url=return_url,
                refresh_url=refresh_url,
                type="account_onboarding",
            )

            return JsonResponse({'url': account_link.url})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='/auth/login/')
@writer_required
def create_account(request):
    if request.method == 'POST':
        try:
            user = request.user
            if user.stripe_account_id:
                # Fetch the Stripe account details to check if it is fully set up
                account = stripe.Account.retrieve(user.stripe_account_id)

                # Check if the account is fully set up
                if account.charges_enabled and account.payouts_enabled:
                    return JsonResponse({'error': 'User already has a fully set up Stripe account.'}, status=400)
                else:
                    # If not fully set up, redirect to the account setup process
                    return JsonResponse({'account': account.id})


            account = stripe.Account.create()
            user.stripe_account_id = account.id
            user.save()
            return JsonResponse({'account': account.id})
        except Exception as e:
            print(f'account/ error: {e}')
            return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='/auth/login/')
@writer_required
def catch_all(request, connected_account_id=None, path=None):
    try:
        return render(request, path)
    except Exception as e:
        print(e)
        return render(request, 'portal/payments/error.html')


@login_required(login_url='/auth/login/')
def create_checkout_session(request, creator_id):
    creator = User.objects.get(public_id=creator_id)
    subscription_plan = SubscriptionPlan.objects.get(writer=creator)

    if not creator.stripe_account_id:
        return JsonResponse({'error': 'Creator does not have a connected Stripe account'}, status=400)

    try:
        # Create a Checkout session for subscription
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Subscription Payment to {creator.first_name} {creator.last_name}',
                        'description': 'Payment for creator content',
                    },
                    'unit_amount': int(int(subscription_plan.price) * 100),  # Amount in cents
                    'recurring': {
                        'interval': 'month',  # Set the interval for the subscription (monthly in this case)
                    },
                },
                'quantity': 1,
            }],
            subscription_data={  # Use subscription_data instead of payment_intent_data for recurring payments
                'application_fee_percent': int(settings.PLATFORM_COST),  # Platform fee percentage
                'transfer_data': {
                    'destination': creator.stripe_account_id,  # Creator's Stripe account ID
                },
            },
            mode='subscription',
            success_url=request.build_absolute_uri(reverse('core-portal:successful-payment')),
            cancel_url=request.build_absolute_uri('/cancel/'),
        )
        return JsonResponse({'id': checkout_session.id})
    except Exception as e:
        print(e)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        print(f'error: Invalid payload: {e}')
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        print(f'error: Invalid signature: {e}')
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session(session)

    return JsonResponse({'status': 'success'}, status=200)


def handle_checkout_session(session):
    try:
        subscriber = User.objects.get(email=session['customer_details']['email'])
        creator_id = session['metadata']['creator_id']  
        creator = User.objects.get(id=creator_id)
        plan = SubscriptionPlan.objects.get(writer=creator)

        subscription, created = Subscription.objects.get_or_create(
            subscriber=subscriber,
            writer=creator,
            defaults={'plan': plan, 'start_date': timezone.now(), 'end_date': timezone.now() + relativedelta(months=1)}
        )

        if not created:
            subscription.active = True
            subscription.start_date = timezone.now()
            subscription.end_date = subscription.start_date + relativedelta(months=1)
            subscription.save()

        return JsonResponse({'status': 'subscription_created'})
    except Exception as e:
        print(f"Error in handling checkout session: {e}")
        return JsonResponse({'error': str(e)}, status=500)
