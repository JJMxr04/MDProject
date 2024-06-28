
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from core.admin.admin import custom_admin_view

urlpatterns = [
    path('admin/dashboard/', custom_admin_view, name='custom_dashboard'),
    path('admin/', admin.site.urls),
    path('api/', include(('core.routers', 'core'), namespace="core-api")),

    # Ensure namespace is 'core-web'  # Correct namespace
]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)