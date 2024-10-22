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
    stripe_account_id = user.stripe_account_id

    if not stripe_account_id:
        return redirect('core-portal:onboarding')

    try:
        account = stripe.Account.retrieve(stripe_account_id)
    except stripe.error.StripeError:
        return redirect('core-portal:onboarding')

    if account['charges_enabled'] and account['details_submitted']:
        try:
            # Fetch account balance
            balance = stripe.Balance.retrieve(stripe_account=stripe_account_id)
            available_balance = balance['available'][0]['amount'] / 100
            pending_balance = balance['pending'][0]['amount'] / 100

            # Fetch active subscriptions and current subscription price
            active_subscriptions = Subscription.objects.writer_active_subscriptions(writer=request.user)
            if SubscriptionPlan.objects.filter(writer=request.user):
                current_subscription_price = SubscriptionPlan.objects.filter(writer=request.user).first().price
            else: 
                current_subscription_price = 0
            # Fetch payouts and last payout
            payouts = stripe.Payout.list(stripe_account=stripe_account_id)
            last_payout = payouts['data'][0] if payouts['data'] else None
            last_payout_amount = last_payout['amount'] / 100 if last_payout else 0
            last_payout_date = last_payout['arrival_date'] if last_payout else 'No payouts yet'

            # Calculate gross income, fees, and net earnings
            total_gross_income = available_balance + last_payout_amount
            stripe_fee = (total_gross_income * 0.029) + 0.30
            application_fee = total_gross_income * (int(settings.PLATFORM_COST) / 100)
            net_earnings = total_gross_income - (stripe_fee + application_fee)

            # Calculations for total earned income, overall application fees, and stripe fees
            total_earned_income = available_balance + pending_balance
            overall_stripe_fees = total_earned_income * 0.029 + 0.30  # Assuming the same 2.9% + $0.30 fee
            overall_application_fees = total_earned_income * (int(settings.PLATFORM_COST) / 100)

        except stripe.error.StripeError:
            available_balance = 0
            last_payout_amount = 0
            last_payout_date = 'No payouts yet'
            stripe_fee = 0
            application_fee = 0
            net_earnings = 0
            total_earned_income = 0
            overall_stripe_fees = 0
            overall_application_fees = 0

        # Pass the data to the template
        context = {
            'active_subscriptions': active_subscriptions,
            'current_subscription_price': current_subscription_price,
            'monthly_income_projection': active_subscriptions * current_subscription_price,
            'available_balance': available_balance,
            'pending_balance': pending_balance,
            'last_payout_amount': last_payout_amount,
            'last_payout_date': last_payout_date,
            'stripe_fee': round(stripe_fee, 2),
            'application_fee': round(application_fee, 2),
            'net_earnings': round(net_earnings, 2),
            'total_earned_income': round(total_earned_income, 2),
            'overall_stripe_fees': round(overall_stripe_fees, 2),
            'overall_application_fees': round(overall_application_fees, 2),
        }
        print(context)

        return render(request, 'portal/blog/writer/writer-dashboard.html', context)

    else:
        return redirect('core-portal:onboarding')
