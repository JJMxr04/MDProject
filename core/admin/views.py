from django.shortcuts import render

def admin_dashboard(request):
    return render(request, 'admin/dashboard/dashboard.html')
