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
    user = request.user

    # Assuming the user model has a field for Stripe account ID
    stripe_account_id = user.stripe_account_id

    if not stripe_account_id:
        # No connected account, redirect to onboarding
        return render(request, 'portal/payments/onboarding.html' ) # Replace 'onboarding_page' with your actual onboarding URL name

    # Fetch the account details from Stripe
    try:
        account = stripe.Account.retrieve(stripe_account_id)
    except stripe.error.StripeError:
        # Handle any potential error here (e.g., log the error)
        return render(request, 'portal/payments/onboarding.html' )
    # Check if the account is fully set up
    if account['charges_enabled'] and account['details_submitted']:
        # Account is fully set up, display the dashboard
         return redirect('core-portal:writer-dashboard') 
    else:
        # Account is not fully set up, redirect to onboarding
        
        return render(request, 'portal/payments/onboarding.html')


@login_required(login_url='/auth/login/')
def successful_payment(request):
    return render(request, 'portal/payments/success.html')
@login_required(login_url='/auth/login/')
def successful_cancel_subscription(request):
    return render(request, 'portal/payments/success-cancel-subscription.html')


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

    # Check if the user already has an active subscription with this creator
    active_subscription = Subscription.objects.filter(
        user=request.user, writer=creator, is_active=True
    ).exists()

    if active_subscription:
        # If there's an active subscription, redirect to the writer's page
        return JsonResponse({'error': 'You already have an active subscription'}, status=400)

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
            subscription_data={
                'application_fee_percent': int(settings.PLATFORM_COST),
                'transfer_data': {
                    'destination': creator.stripe_account_id,  # Creator's Stripe account ID
                },
            },
            mode='subscription',
            success_url=request.build_absolute_uri(reverse('core-portal:successful-payment')),
            cancel_url=request.build_absolute_uri('/cancel/'),
            customer_email=request.user.email,  # Use the logged-in user's email
            metadata={
                'creator_id': creator.id
            },
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
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({'error': 'Invalid signature'}, status=400)
    print(event['type'])
    print(event)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        handle_checkout_session(session)

    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        handle_failed_payment(invoice)

    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        handle_successful_payment(invoice)

    elif event['type'] == 'customer.subscription.updated':
        sub = event['data']['object']
        handle_subscription_update(sub)

    
    elif event['type'] == 'customer.subscription.deleted':
        sub = event['data']['object']
        handle_subscription_deleted(sub)

    return JsonResponse({'status': 'success'}, status=200)



def handle_checkout_session(session):
    try:
        subscriber = User.objects.get(email=session['customer_details']['email'])
        customer_id = session['customer']
        creator_id = session['metadata']['creator_id']
        subscription_id = session['subscription']
        creator = User.objects.get(id=creator_id)
        plan = SubscriptionPlan.objects.get(writer=creator)

        if not subscriber.stripe_customer_id:
            subscriber.stripe_customer_id = customer_id
            subscriber.save()

        # Check if there's an existing subscription for this user and creator
        existing_subscription = Subscription.objects.filter(
            subscriber=subscriber,
            writer=creator
        ).first()

        # If an existing subscription is found, update it; otherwise, create a new one
        if existing_subscription:
            existing_subscription.active = True
            existing_subscription.start_date = timezone.now()
            existing_subscription.end_date = existing_subscription.start_date + relativedelta(months=1)
            existing_subscription.stripe_subscription_id = subscription_id
            existing_subscription.stripe_customer_id = customer_id
            existing_subscription.plan = plan
            existing_subscription.save()
            subscription = existing_subscription
        else:
            # Create a new subscription
            subscription = Subscription.objects.create(
                subscriber=subscriber,
                writer=creator,
                plan=plan,
                start_date=timezone.now(),
                end_date=timezone.now() + relativedelta(months=1),
                stripe_subscription_id=subscription_id,
                stripe_customer_id=customer_id,
                active=True
            )

        # Create an invoice for the initial payment (assuming the first month is paid upfront)
        Invoice.objects.create(
            user=subscriber,
            subscription=subscription,
            amount=plan.price,  # Initial price of the subscription plan
            status='paid',  # Mark it as paid since the session completed
            stripe_invoice_id=session['id']  # Use session ID as the initial invoice reference
        )

        return JsonResponse({'status': 'subscription_created'})
    except Exception as e:
        print(f'Error: {e}')
        return JsonResponse({'error': str(e)}, status=500)



def handle_failed_payment(invoice):
    try:
        customer_id = invoice['customer']
        subscription_id = invoice['subscription']
        stripe_invoice_id = invoice['id']
        amount_due = invoice['amount_due'] / 100  # Convert cents to dollars

        subscriber = User.objects.get(stripe_customer_id=customer_id)
        subscription = Subscription.objects.get(
            subscriber=subscriber,
            stripe_subscription_id=subscription_id
        )

        # Update or create the failed invoice
        Invoice.objects.update_or_create(
            stripe_invoice_id=stripe_invoice_id,
            defaults={
                'user': subscriber,
                'subscription': subscription,
                'amount': amount_due,
                'status': 'failed',
            }
        )

        # Optionally, deactivate the subscription
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
        amount_paid = invoice['amount_paid'] / 100  # Convert cents to dollars

        subscriber = User.objects.get(stripe_customer_id=customer_id)

        subscription = Subscription.objects.get(
            subscriber=subscriber,
            stripe_subscription_id=subscription_id
        )

        # Update or create the invoice as paid
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

    try:
        # Retrieve the Stripe customer and subscription IDs from the invoice
        customer_id = invoice['customer']
        subscription_id = invoice['subscription']
        stripe_invoice_id = invoice['id']  # Stripe invoice ID
        amount_paid = invoice['amount_paid'] / 100  # Convert cents to dollars

        # Find the user by their Stripe customer ID
        subscriber = User.objects.get(stripe_customer_id=customer_id)

        # Retrieve the corresponding subscription
        subscription = Subscription.objects.get(
            subscriber=subscriber,
            stripe_subscription_id=subscription_id
        )

        # Create or update the invoice record
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


def handle_subscription_update(sub):

        try:
            subscription_id = sub['id']
            status=sub['status']

            subscription = Subscription.objects.get(
                stripe_subscription_id=subscription_id
            )

            if status == 'active':
                subscription.active = True
            else:
                subscription.active = False
            subscription.save()

        except Exception as e:
            print(f"Error handling subscription update: {e}")


def handle_subscription_deleted(sub):

        try:
            subscription_id = sub['id']
            status=sub['status']

            subscription = Subscription.objects.get(
                stripe_subscription_id=subscription_id
            )


            subscription.active = False
            subscription.save()

        except Exception as e:
            print(f"Error handling subscription deleted: {e}")


@login_required(login_url='/auth/login/')
def recent_invoices_and_subscriptions(request):
    user = request.user

    # Fetch the active subscriptions from the database
    active_subscriptions = Subscription.objects.filter(subscriber=user, active=True)

    # Fetch recent invoices from Stripe
    recent_invoices = []
    if user.stripe_customer_id:
        try:
            invoices = stripe.Invoice.list(customer=user.stripe_customer_id, limit=10)
            recent_invoices = invoices.data
            for invoice in recent_invoices:
                invoice.amount_due_in_dollars = invoice.amount_due / 100  # Convert cents to dollars
        except stripe.error.StripeError as e:
            print(f"Error fetching invoices from Stripe: {e}")

    # Render the template with the invoices and subscriptions data
    return render(request, 'portal/payments/recent_invoices_and_subscriptions.html', {
        'active_subscriptions': active_subscriptions,
        'recent_invoices': recent_invoices,
    })
@login_required(login_url='/auth/login/')
def invoice_detail(request, invoice_id):
    user = request.user
    invoice = None
    if user.stripe_customer_id:
        try:
            # Retrieve the invoice from Stripe
            invoice = stripe.Invoice.retrieve(invoice_id)
            
            # Process invoice amount_due
            if invoice.amount_due is not None:
                invoice.amount_due = invoice.amount_due / 100

            # Process item amounts in lines.data
            for item in invoice.lines.data:
                if item.amount is not None:
                    item.amount = item.amount / 100

        except stripe.error.StripeError as e:
            print(f"Error fetching invoice: {e}")

    return render(request, 'portal/payments/invoice_detail.html', {'invoice': invoice})

@login_required(login_url='/auth/login/')
def cancel_subscription(request, subscription_id):
    try:
        # Get the subscription object from the database
        subscription = Subscription.objects.get(id=subscription_id, subscriber=request.user)

        # Call Stripe API to cancel the subscription
        stripe.Subscription.delete(subscription.stripe_subscription_id)

        # Update the subscription status in the database
        subscription.active = False
        subscription.end_date = timezone.now()
        subscription.save()

        # Optionally, create an invoice record for the cancellation
        Invoice.objects.create(
            user=request.user,
            subscription=subscription,
            amount=0,  # Amount could be set based on your policy (e.g., prorated amount)
            status='canceled',
            stripe_invoice_id=None  # Set to None as there's no associated invoice for cancellation
        )

        # Redirect to a success page or display a success message
        return redirect('core-portal:successful-cancel-subscription')
    except Subscription.DoesNotExist:
        return JsonResponse({'error': 'Subscription not found'}, status=404)
    except stripe.error.StripeError as e:
        return JsonResponse({'error': f'Stripe error: {str(e)}'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Error: {str(e)}'}, status=500)

