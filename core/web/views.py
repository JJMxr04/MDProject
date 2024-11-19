from django.shortcuts import render


def home(request):

    return render(request, 'public/home.html')


def about(request):
    return render(request, 'public/aboutUs.html')

def privacy_policy(request):
    return render(request, 'public/privacyPolicy.html')

def services(request):
    return render(request, 'public/service.html')

def gameRules(request):
    return render(request, 'public/gameRules.html')