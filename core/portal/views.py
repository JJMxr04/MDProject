from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.

# Create your views here.
@login_required(login_url='/auth/login/')
def portal_dashboard(request):


    # If the request method is not POST, render the login page normally
    return render(request, 'portal/dashboard/dashboard.html')
