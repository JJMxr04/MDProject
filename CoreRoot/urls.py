
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import path, include
from core.admin.admin import custom_admin_view
from core.auth.views.password_reset import BrandedPasswordResetView
from core.billing.views.webhook import stripe_webhook
from core.event.views.webhooks.sportsgameodds import SportsGameOddsWebhookView
from core.views import csp_report, healthz, portal_or_404, robots_txt
from django.contrib.auth import views as auth_views


urlpatterns = [
    # path('admin/dashboard/', custom_admin_view, name='admin_dashboard'),
    path('admin/', include(('core.admin.urls', 'core-admin'), namespace='core-admin')),
    path('admin/', admin.site.urls),
    path('api/', include(('core.event.api_urls', 'core-event-api'), namespace='core-event-api')),
    # Secure portal JSON surface for the Alpine islands (plan js-portal-security).
    # Session-first auth, IsAuthenticated default, envelope + request_id, scoped
    # throttles — all bound via core.api.base.V1ViewMixin.
    path('api/v1/', include('core.api.urls')),
    # Inbound webhook from the aggregator service (plan §4). HMAC-signed
    # payloads update Event/Market/Selection state and run the existing
    # match-completion / game-reopen hooks.
    path('sportgameodds/webhook', SportsGameOddsWebhookView.as_view(),
         name='sportgameodds-webhook'),
    # Stripe → MDProject. Signature-verified, idempotent (StripeWebhookEvent).
    # See core/billing/views/webhook.py.
    path('billing/stripe/webhook', stripe_webhook, name='billing-stripe-webhook'),
    path('', include(('core.web.urls', 'core-web'), namespace='core-web')),
    path('auth/', include(('core.auth.urls', 'core-auth'), namespace='core-auth')),
    path("robots.txt", robots_txt, name="robots_txt"),
    # CSP violation report sink (report-only phase of S-7).
    path("csp-report/", csp_report, name="csp-report"),
    # Container health probe — Coolify / docker / k8s readiness check.
    path("healthz", healthz, name="healthz"),
    path('web/portal/', include(('core.portal.urls', 'core-portal'), namespace='core-portal')),
    # path('mail/', include(('core.mail.urls', 'core-mail'), namespace='core-mail')), # Updated path

    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    # Ensure namespace is 'core-web'  # Correct namespace
    # path('event/', include(('core.event.urls', 'core-event'), namespace='core-event')),
    path('reset_password/', BrandedPasswordResetView.as_view(), name='reset_password'),
    path('reset_password_sent/',auth_views.PasswordResetDoneView.as_view(template_name='authorization/password-reset-sent.html'),name='password_reset_done'),
    path('reset/<uidb64>/<token>',auth_views.PasswordResetConfirmView.as_view(template_name='authorization/password-reset-form.html'),name='password_reset_confirm'),
    path('reset_password_complete/',auth_views.PasswordResetCompleteView.as_view(template_name='authorization/password-reset-complete.html'),name='password_reset_complete'),
    
    

]


urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# django-silk dashboard — only mounted when SILK_ENABLED. The view layer
# is still gated by SILKY_PERMISSIONS (superuser-only), but omitting the
# route entirely when off means the URL 404s instead of returning a
# login redirect, which is the safer signal to an unauth'd probe.
if getattr(settings, "SILK_ENABLED", False):
    urlpatterns += [path("silk/", include("silk.urls", namespace="silk"))]


# Custom 404 — paths under /web/portal/ and /admin/ redirect to the
# public landing instead of showing a Django 404 page. Everything else
# gets a plain 404.
handler404 = "core.views.portal_or_404"