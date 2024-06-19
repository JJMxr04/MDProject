
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(('core.routers', 'core'), namespace="core-api")),
    path('', include(('core.web.urls', 'core-web'), namespace='core-web')),
    path('auth/', include(('core.auth.urls', 'core-auth'), namespace='core-auth')),
    path('web/portal/', include(('core.portal.urls', 'core-portal'), namespace='core-portal')),
    path('web/admin/', include(('core.admin.urls', 'core-admin'), namespace='core-admin')),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Ensure namespace is 'core-web'  # Correct namespace
]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)