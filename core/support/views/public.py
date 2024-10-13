from django.shortcuts import render

def contact_us(request):

    return render(request, 'public/support/contact-us.html')