from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.shortcuts import render, redirect  # Import redirect
import stripe
import os
from django.contrib.auth.decorators import login_required
from core.blog.writer.decorator import writer_required

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
# @login_required(login_url='/auth/login/')
# @writer_required
# def catch_all(request, connected_account_id=None, path=None):
#     if settings.STATICFILES_DIRS:
#         if path and os.path.exists(os.path.join(settings.STATICFILES_DIRS[0], path)):
#             # Serve the static file if it exists
#             with open(os.path.join(settings.STATICFILES_DIRS[0], path), 'rb') as f:
#                 return HttpResponse(f.read(), content_type="text/html")
#         else:
#             # Serve the frontend index.html if no static file is found
#             with open(os.path.join(settings.STATICFILES_DIRS[0], 'index.html'), 'rb') as f:
#                 return HttpResponse(f.read(), content_type="text/html")
#     # Redirect to the portal dashboard if static files directory is not configured
#     return redirect('core-portal:portal-dashboard')
