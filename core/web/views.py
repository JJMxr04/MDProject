from django.shortcuts import redirect, render


def home(request):

    return render(request, 'public/home.html')


def about(request):
    return render(request, 'public/aboutUs.html')

def privacy_policy(request):
    return render(request, 'public/privacyPolicy.html')

def terms(request):
    return render(request, 'public/terms.html')

def contact(request):
    return render(request, 'public/contact.html')

def services(request):
    return render(request, 'public/service.html')

def gameRules(request):
    """Old public URL — rules now live in the auth-gated portal so only
    real users see them. ``login_required`` on ``portal-rules`` will bounce
    anonymous traffic to the login page; signed-in users land directly."""
    return redirect('core-portal:portal-rules')
