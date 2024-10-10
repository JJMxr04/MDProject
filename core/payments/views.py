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
from core.payments.models import Invoice


User = get_user_model()

# Set up the Stripe API key
stripe.api_key = settings.STRIPE_API_KEY
stripe.api_version = '2023-10-16'


@login_required(login_url='/auth/login/')
def onboarding_page(request):
    if request.user.stripe_account_id:
        return redirect('core-portal:writer-subscription-plan')
    return render(request, 'portal/payments/onboarding.html')


def successful_payment(request):
    return render(request, 'portal/payments/success.html')


@login_required(login_url='/auth/login/')
@writer_required
def create_account_link(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            connected_account_id = data.get('account')
            if not connected_account_id:
                return JsonResponse({'error': 'Connected account ID is required.'}, status=400)

            return_url = f"https://yourdomain.com/web/portal/payments/return/{connected_account_id}/"
            refresh_url = f"https://yourdomain.com/web/portal/payments/return/{connected_account_id}/"

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
                account = stripe.Account.retrieve(user.stripe_account_id)
                if account.charges_enabled and account.payouts_enabled:
                    return JsonResponse({'error': 'User already has a fully set up Stripe account.'}, status=400)
                return JsonResponse({'account': account.id})

            account = stripe.Account.create()
            user.stripe_account_id = account.id
            user.save()
            return JsonResponse({'account': account.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


@login_required(login_url='/auth/login/')
@writer_required
def catch_all(request, connected_account_id=None, path=None):
    try:
        return render(request, path)
    except Exception as e:
        return render(request, 'portal/payments/error.html')


@login_required(login_url='/auth/login/')
def create_checkout_session(request, creator_id):
    creator = User.objects.get(public_id=creator_id)
    subscription_plan = SubscriptionPlan.objects.get(writer=creator)

    if not creator.stripe_account_id:
        return JsonResponse({'error': 'Creator does not have a connected Stripe account'}, status=400)

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'Subscription Payment to {creator.first_name} {creator.last_name}',
                        'description': 'Payment for creator content',
                    },
                    'unit_amount': int(int(subscription_plan.price) * 100),
                    'recurring': {'interval': 'daily'},
                },
                'quantity': 1,
            }],
            subscription_data={  
                'application_fee_percent': settings.PLATFORM_COST,
                'transfer_data': {'destination': creator.stripe_account_id},
            },
            mode='subscription',
            success_url=request.build_absolute_uri(reverse('core-portal:successful-payment')),
            cancel_url=request.build_absolute_uri('/cancel/'),
            metadata={'creator_id': creator.id},
        )
        return JsonResponse({'id': checkout_session.id})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session(session)

    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        handle_failed_payment(invoice)

    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        handle_successful_payment(invoice)

    return JsonResponse({'status': 'success'}, status=200)


def handle_checkout_session(session):
    try:
        subscriber = User.objects.get(email=session['customer_details']['email'])
        creator_id = session['metadata']['creator_id']
        subscription_id = session['subscription']
        creator = User.objects.get(id=creator_id)
        plan = SubscriptionPlan.objects.get(writer=creator)

        subscription, created = Subscription.objects.get_or_create(
            subscriber=subscriber,
            writer=creator,
            defaults={
                'plan': plan,
                'start_date': timezone.now(),
                'end_date': timezone.now() + relativedelta(months=1),
                'stripe_subscription_id': subscription_id,
                'stripe_customer_id': session['customer']
            }
        )

        if not created:
            subscription.active = True
            subscription.start_date = timezone.now()
            subscription.end_date = subscription.start_date + relativedelta(months=1)
            subscription.save()

        Invoice.objects.create(
            user=subscriber,
            subscription=subscription,
            amount=plan.price,
            status='paid',
            stripe_invoice_id=session['id']
        )
    except Exception as e:
        print(f'Error: {e}')
        return JsonResponse({'error': str(e)}, status=500)


def handle_failed_payment(invoice):
    try:
        customer_id = invoice['customer']
        subscription_id = invoice['subscription']
        stripe_invoice_id = invoice['id']
        amount_due = invoice['amount_due'] / 100

        subscriber = User.objects.get(stripe_customer_id=customer_id)

        subscription = Subscription.objects.get(
            subscriber=subscriber,
            stripe_subscription_id=subscription_id
        )

        Invoice.objects.update_or_create(
            stripe_invoice_id=stripe_invoice_id,
            defaults={
                'user': subscriber,
                'subscription': subscription,
                'amount': amount_due,
                'status': 'failed',
            }
        )

        subscription.active = False
        subscription.save()
        print(f"Invoice {stripe_invoice_id} for user {subscriber.email} recorded as failed. Subscription deactivated.")
    except Exception as e:
        print(f"Error handling failed payment: {e}")


def handle_successful_payment(invoice):
    try:
        customer_id = invoice['customer']
        subscription_id = invoice['subscription']
        stripe_invoice_id = invoice['id']
        amount_paid = invoice['amount_paid'] / 100

        subscriber = User.objects.get(stripe_customer_id=customer_id)

        subscription = Subscription.objects.get(
            subscriber=subscriber,
            stripe_subscription_id=subscription_id
        )

        Invoice.objects.update_or_create(
            stripe_invoice_id=stripe_invoice_id,
            defaults={
                'user': subscriber,
                'subscription': subscription,
                'amount': amount_paid,
                'status': 'paid',
            }
        )
        print(f"Invoice {stripe_invoice_id} for user {subscriber.email} recorded as paid.")
    except Exception as e:
        print(f"Error handling successful payment: {e}")
