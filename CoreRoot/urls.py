
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import path, include
from core.admin.admin import custom_admin_view
from core.views import robots_txt

urlpatterns = [
    path('admin/dashboard/', custom_admin_view, name='admin_dashboard'),
    path('admin/', admin.site.urls),
    # path('api/', include(('core.routers', 'core'), namespace="core-api")),
    path('', include(('core.web.urls', 'core-web'), namespace='core-web')),
    path('auth/', include(('core.auth.urls', 'core-auth'), namespace='core-auth')),
    path("robots.txt", robots_txt, name="robots_txt"),
    path('web/portal/', include(('core.portal.urls', 'core-portal'), namespace='core-portal')),
    # path('admin/web/', include(('core.admin.urls', 'core-admin'), namespace='core-admin')),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Ensure namespace is 'core-web'  # Correct namespace
    # path('event/', include(('core.event.urls', 'core-event'), namespace='core-event')),
]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)