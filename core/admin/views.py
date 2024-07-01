from django.contrib import admin
from django.urls import path
from django.contrib.admin.views.decorators import staff_member_required
from django.template.response import TemplateResponse

@staff_member_required
def custom_admin_view(request):
    context = dict(
        admin.site.each_context(request),
        title='Custom Dashboard',
    )
    return TemplateResponse(request, "admin/dashboard/dashboard.html", context)


