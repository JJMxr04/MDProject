from django.shortcuts import render


def home(request):

    return render(request, 'public/home.html')


def about(request):
    return render(request, 'public/about.html', {'title': 'About'})

def privacy_policy(request):
    return render(request, 'public/privacyPolicy.html')