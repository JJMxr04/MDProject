from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from core.blog.writer.decorator import writer_required
from django.conf import settings
import stripe
import os
from core.blog.client.models import Subscription
from core.blog.writer.models import SubscriptionPlan


# Set up Stripe API key and version
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
        return redirect('core-portal:onboarding')

    # Fetch the account details from Stripe
    try:
        account = stripe.Account.retrieve(stripe_account_id)
    except stripe.error.StripeError:
        # Handle any potential error here (e.g., log the error)
        return redirect('core-portal:onboarding')

    # Check if the account is fully set up
    if account['charges_enabled'] and account['details_submitted']:
        # Account is fully set up, fetch additional details

        try:

            active_subscriptions = len()
            # Fetch account balance
            balance = stripe.Balance.retrieve(stripe_account=stripe_account_id)
            print(f'Balance: {balance}')
            available_balance = balance['available'][0]['amount'] / 100
            pending_balance = balance['pending'][0]['amount'] / 100  # Convert from cents to dollars


            active_subcriptions = Subscription.objects.writer_active_subscriptions(writer=request.user)
            current_subscription_price= SubscriptionPlan.objects.filter(wrier=request.user).price,
            # Fetch the last payout
            payouts = stripe.Payout.list(stripe_account=stripe_account_id)
            print(f'Payouts: {payouts}')
            last_payout = payouts['data'][0] if payouts['data'] else None
            last_payout_amount = last_payout['amount'] / 100 if last_payout else 0
            last_payout_date = last_payout['arrival_date'] if last_payout else 'No payouts yet'

            # Calculate Stripe fee and application fee (if applicable)
            # Assuming Stripe charges 2.9% + $0.30 per transaction and the application fee is 10% of the earnings.
            total_gross_income = available_balance + last_payout_amount  # Combine payout and available balance
            stripe_fee = (total_gross_income * 0.029) + 0.30  # Stripe fee calculation
            application_fee = total_gross_income *  (settings.PLATFORM_COST/100) # Application fee as 10% of total gross income
            net_earnings = total_gross_income - (stripe_fee + application_fee)

        except stripe.error.StripeError:
            # Handle any errors related to fetching balance or payouts
            available_balance = 0
            last_payout_amount = 0
            last_payout_date = 'No payouts yet'
            stripe_fee = 0
            application_fee = 0
            net_earnings = 0

        # Pass the data to the template
        context = {
            'active_subcriptions': active_subcriptions,
            'current_subscription_price': current_subscription_price,
            'monthly_income_projection': active_subscriptions * current_subscription_price,
            'available_balance': available_balance,
            'pending_balance': pending_balance,
            'last_payout_amount': last_payout_amount,
            'last_payout_date': last_payout_date,
            'stripe_fee': round(stripe_fee, 2),
            'application_fee': round(application_fee, 2),
            'net_earnings': round(net_earnings, 2),
        }
        return render(request, 'portal/blog/writer/writer-dashboard.html', context)

    else:
        # Account is not fully set up, redirect to onboarding
        return redirect('core-portal:onboarding')
