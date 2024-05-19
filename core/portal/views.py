from django.shortcuts import render

# Create your views here.

# Create your views here.
def portal_dashboard(request):


    # If the request method is not POST, render the login page normally
    return render(request, 'dashboard/dashboard.html')
