import uuid

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from core.billing.services.customer import (
    StripeCustomerError,
    create_customer as stripe_create_customer,
    reconnect_customer as stripe_reconnect_customer,
)
from core.billing.services import aggrigator_internal
from core.billing.services.subscription_sync import (
    SubscriptionSyncError,
    refresh_from_stripe as subscription_refresh_from_stripe,
)

from .models import User


# ---- click-to-reveal helpers ----
#
# Pattern: masked summary + <details> reveal + copy-to-clipboard button.
# Zero-JS reveal via native <details>; the copy button is a 1-liner.
# Used for any field that ops can read by mistake over a shoulder
# (customer IDs, external IDs, API keys) — never the value itself stays
# on screen unless the operator clicked.

_COPY_BTN_JS = (
    "navigator.clipboard.writeText(this.previousElementSibling.textContent);"
    "this.textContent='copied';"
    "setTimeout(()=>this.textContent='copy',1200);"
)


def _reveal(masked: str, full: str, *, suffix_html: str = '') -> str:
    """Render a masked summary that expands to the full value + copy button.

    ``suffix_html`` is appended *after* the code block when revealed —
    used by the Stripe customer field to add a Dashboard click-through.
    """
    if not full:
        return '—'
    return format_html(
        '<details style="display:inline-block">'
        '<summary style="cursor:pointer;list-style:none">'
        '<code>{}</code> <span style="opacity:.6">▸</span>'
        '</summary>'
        '<div style="margin-top:4px">'
        '<code>{}</code> '
        '<button type="button" style="font-size:11px;padding:1px 6px" '
        'onclick="{}">copy</button>{}'
        '</div></details>',
        masked, full, mark_safe(_COPY_BTN_JS), mark_safe(suffix_html),
    )


def _mask_id(value: str, *, keep: int = 4) -> str:
    """Show only the last ``keep`` chars; mask the rest with bullets.

    For prefixed Stripe IDs like ``cus_UXKRWgDIfKTOqR`` keep the ``cus_``
    so the operator knows the type at a glance.
    """
    if not value:
        return ''
    head = ''
    body = value
    if '_' in value[:8]:
        head, _, body = value.partition('_')
        head += '_'
    if len(body) <= keep:
        return f'{head}{"•" * len(body)}'
    return f'{head}{"•" * (len(body) - keep)}{body[-keep:]}'


def _mask_uuid(value) -> str:
    if not value:
        return ''
    s = str(value)
    # UUIDs are 36 chars with dashes — show only the trailing block.
    return f'…{s[-12:]}'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    # Adds the Reconnect / Create-new Stripe buttons to the
    # object-tools row at the top of the change form. The template
    # extends jazzmin/admin's default — block override only.
    change_form_template = "admin/core_user/user/change_form.html"

    list_display = [
        'email', 'username',
        'subscription_tier', 'subscription_status', 'trial_end_display',
        'stripe_customer_link', 'aggrigator_external_id_display',
        'last_login', 'is_staff', 'is_admin',
    ]
    search_fields = [
        'email', 'username', 'first_name', 'last_name',
        'stripe_customer_id', 'aggrigator_external_id',
    ]

    list_filter = [
        'subscription__plan__code', 'subscription__status',
        'is_staff', 'is_admin', 'is_active', 'activated_link', 'groups',
    ]
    list_select_related = ('subscription', 'subscription__plan')
    ordering = ['-created']

    fieldsets = (
        (None, {'fields': ['username', 'password']}),
        ('Personal Information', {'fields': ['email', 'first_name', 'last_name', 'bio']}),
        ('Subscription & Integration', {
            'fields': [
                'subscription_tier', 'subscription_status', 'trial_end_display',
                'stripe_customer_display', 'aggrigator_external_id_display',
                'aggrigator_api_key_display',
            ],
            'description': (
                "Subscription tier/status are owned by the billing app and "
                "updated by Stripe webhooks — edit on the Subscription page. "
                "The aggrigator API key is shown masked; rotate via "
                "<code>aggrigator_internal.rotate_api_key</code>."
            ),
        }),
        ('Permissions', {'fields': ['activated_link', 'is_staff', 'is_admin', 'is_active', 'is_superuser', 'groups', 'user_permissions']}),
        ('Important Dates', {'fields': ['last_login', 'created', 'updated']}),
    )
    readonly_fields = [
        'created', 'updated', 'is_superuser', 'is_active', 'last_login',
        'subscription_tier', 'subscription_status', 'trial_end_display',
        'stripe_customer_display', 'aggrigator_external_id_display',
        'aggrigator_api_key_display',
    ]

    # ---- Stripe customer actions (Reconnect / Create new) ----

    def get_urls(self):
        """Mount two POST-only routes alongside the standard admin URLs.

        Named ``admin:core_user_user_stripe_reconnect`` /
        ``admin:core_user_user_stripe_create`` (matches the
        ``<app>_<model>_<action>`` convention so ``reverse()`` works
        cleanly from ``stripe_customer_display``)."""
        urls = super().get_urls()
        custom = [
            path(
                "<uuid:user_id>/stripe-reconnect/",
                self.admin_site.admin_view(self.stripe_reconnect_view),
                name="core_user_user_stripe_reconnect",
            ),
            path(
                "<uuid:user_id>/stripe-create/",
                self.admin_site.admin_view(self.stripe_create_view),
                name="core_user_user_stripe_create",
            ),
            path(
                "<uuid:user_id>/aggrigator-provision/",
                self.admin_site.admin_view(self.aggrigator_provision_view),
                name="core_user_user_aggrigator_provision",
            ),
            path(
                "<uuid:user_id>/aggrigator-rotate/",
                self.admin_site.admin_view(self.aggrigator_rotate_view),
                name="core_user_user_aggrigator_rotate",
            ),
            path(
                "<uuid:user_id>/subscription-refresh/",
                self.admin_site.admin_view(self.subscription_refresh_view),
                name="core_user_user_subscription_refresh",
            ),
        ]
        # Custom URLs first so the int-converter doesn't fight the
        # default ``<path:object_id>`` change-view pattern.
        return custom + urls

    @method_decorator(require_POST)
    def stripe_reconnect_view(self, request, user_id: uuid.UUID):
        """Search Stripe for a Customer matching the user's email and
        link it. No-ops with an info message when nothing matches —
        operators can fall back to Create-new manually."""
        if not request.user.is_staff:
            messages.error(request, "Staff only.")
            return HttpResponseRedirect(reverse("admin:index"))
        user = get_object_or_404(User, pk=user_id)
        try:
            cust_id = stripe_reconnect_customer(user)
        except StripeCustomerError as exc:
            messages.error(
                request,
                f"Stripe reconnect failed for {user.email}: {exc.user_message}",
            )
            return self._redirect_to_user(user_id)
        if cust_id is None:
            messages.warning(
                request,
                (
                    f"No Stripe Customer with email {user.email} found in the "
                    "current Stripe account. Use Create-new to mint a fresh one."
                ),
            )
        else:
            messages.success(
                request,
                f"Linked existing Stripe Customer {cust_id} to {user.email}.",
            )
        return self._redirect_to_user(user_id)

    @method_decorator(require_POST)
    def stripe_create_view(self, request, user_id: uuid.UUID):
        """Create a fresh ``cus_...`` and overwrite the user's stored id.

        Destructive in the sense that the previous id is dropped from
        MDProject (the Stripe-side Customer is left in place). Use the
        ``reset_stripe_customers`` management command if you need
        bulk delete-and-recreate."""
        if not request.user.is_staff:
            messages.error(request, "Staff only.")
            return HttpResponseRedirect(reverse("admin:index"))
        user = get_object_or_404(User, pk=user_id)
        old_id = user.stripe_customer_id
        try:
            cust_id = stripe_create_customer(user)
        except StripeCustomerError as exc:
            messages.error(
                request,
                f"Stripe Customer create failed for {user.email}: {exc.user_message}",
            )
            return self._redirect_to_user(user_id)
        if old_id:
            messages.success(
                request,
                f"Replaced Stripe Customer {old_id} → {cust_id} for {user.email}.",
            )
        else:
            messages.success(
                request,
                f"Created Stripe Customer {cust_id} for {user.email}.",
            )
        return self._redirect_to_user(user_id)

    # ---- Aggrigator tenant_user actions ----

    @method_decorator(require_POST)
    def aggrigator_provision_view(self, request, user_id: uuid.UUID):
        """Get-or-create the aggrigator tenant_user for this MDProject
        User. Mirrors the per-user logic in the
        ``backfill_aggrigator_users`` management command — provision,
        and rotate if the aggrigator already had the row but we lost
        the key on this side. Old users that pre-date the aggrigator
        integration use this to catch up without a full backfill run."""
        if not request.user.is_staff:
            messages.error(request, "Staff only.")
            return HttpResponseRedirect(reverse("admin:index"))
        user = get_object_or_404(User, pk=user_id)
        try:
            result = aggrigator_internal.get_or_create_tenant_user(user)
        except aggrigator_internal.ParadiseError as exc:
            messages.error(
                request,
                f"Aggrigator provisioning failed for {user.email}: {exc}",
            )
            return self._redirect_to_user(user_id)
        except Exception as exc:
            messages.error(
                request,
                f"Aggrigator provisioning failed for {user.email}: {exc}",
            )
            return self._redirect_to_user(user_id)

        if result.created:
            verb = "Provisioned new"
        elif result.rotated:
            verb = "Recovered (rotated key for existing)"
        else:
            verb = "Synced"
        messages.success(
            request,
            f"{verb} aggrigator tenant_user for {user.email} "
            f"(external_id {result.external_id}).",
        )
        return self._redirect_to_user(user_id)

    @method_decorator(require_POST)
    def aggrigator_rotate_view(self, request, user_id: uuid.UUID):
        """Force-rotate the aggrigator API key. Revokes every existing
        key on the aggrigator side and stores the new plaintext on the
        User row. Use when the stored key is suspected leaked or when
        recovering from a key loss without re-provisioning."""
        if not request.user.is_staff:
            messages.error(request, "Staff only.")
            return HttpResponseRedirect(reverse("admin:index"))
        user = get_object_or_404(User, pk=user_id)
        try:
            new_key = aggrigator_internal.rotate_api_key(user)
        except aggrigator_internal.ParadiseError as exc:
            messages.error(
                request,
                f"Aggrigator key rotation failed for {user.email}: {exc}",
            )
            return self._redirect_to_user(user_id)
        if not new_key:
            messages.error(
                request,
                f"Aggrigator returned no api_key on rotate for {user.email}.",
            )
            return self._redirect_to_user(user_id)
        User.objects.filter(pk=user.pk).update(
            aggrigator_api_key=new_key,
            aggrigator_external_id=user.public_id,
        )
        messages.success(
            request,
            f"Rotated aggrigator API key for {user.email}. The old key "
            "is now revoked.",
        )
        return self._redirect_to_user(user_id)

    # ---- Subscription refresh ----

    @method_decorator(require_POST)
    def subscription_refresh_view(self, request, user_id: uuid.UUID):
        """Pull the user's live Stripe Subscription state and re-apply
        it to the local row + the aggrigator's entitlement mirror.
        Same field mapping the webhook handler uses — for when an
        operator suspects the local Subscription drifted from Stripe
        (missed webhook delivery, manual Dashboard edit, DB restore)."""
        if not request.user.is_staff:
            messages.error(request, "Staff only.")
            return HttpResponseRedirect(reverse("admin:index"))
        user = get_object_or_404(User, pk=user_id)
        try:
            report = subscription_refresh_from_stripe(user)
        except SubscriptionSyncError as exc:
            messages.error(
                request,
                f"Subscription refresh failed for {user.email}: {exc.user_message}",
            )
            return self._redirect_to_user(user_id)
        except Exception as exc:
            messages.error(
                request,
                f"Subscription refresh failed for {user.email}: {exc}",
            )
            return self._redirect_to_user(user_id)

        if not report.found_on_stripe:
            messages.warning(
                request,
                f"No Stripe Subscription on file for {user.email} — "
                "reset local row to FREE.",
            )
        else:
            messages.success(
                request,
                f"Refreshed {user.email}: plan={report.plan_code} "
                f"status={report.status} (Stripe id "
                f"{report.stripe_subscription_id}).",
            )
        if report.found_on_stripe and not report.aggrigator_synced:
            messages.warning(
                request,
                "Local row updated, but the aggrigator entitlement "
                "push failed — re-run after the aggrigator recovers, "
                "or check PARADISE_SECRET / AGGRIGATOR_BASE_URL.",
            )
        return self._redirect_to_user(user_id)

    def _redirect_to_user(self, user_id: uuid.UUID) -> HttpResponseRedirect:
        return HttpResponseRedirect(
            reverse("admin:core_user_user_change", args=[user_id]),
        )

    # ---- subscription column helpers ----

    @admin.display(description='Tier', ordering='subscription__plan__code')
    def subscription_tier(self, obj):
        sub = getattr(obj, 'subscription', None)
        return sub.plan.code if sub and sub.plan_id else '—'

    @admin.display(description='Sub status', ordering='subscription__status')
    def subscription_status(self, obj):
        sub = getattr(obj, 'subscription', None)
        return sub.status if sub else '—'

    @admin.display(description='Trial ends', ordering='subscription__trial_end')
    def trial_end_display(self, obj):
        sub = getattr(obj, 'subscription', None)
        return sub.trial_end if sub and sub.trial_end else '—'

    @admin.display(description='Stripe customer', ordering='stripe_customer_id')
    def stripe_customer_link(self, obj):
        """Used on the changelist: masked + reveal + copy."""
        cid = obj.stripe_customer_id
        if not cid:
            return '—'
        url = f'https://dashboard.stripe.com/test/customers/{cid}'
        suffix = (
            f' <a href="{url}" target="_blank" rel="noopener" '
            'style="font-size:11px">open in Stripe ↗</a>'
        )
        return _reveal(_mask_id(cid), cid, suffix_html=suffix)

    @admin.display(description='Stripe customer')
    def stripe_customer_display(self, obj):
        """Detail-page version of stripe_customer_link — same renderer.

        The Reconnect / Create-new buttons live in the ``object-tools``
        row at the top of the change form (see
        ``change_form_template``) — putting them here would nest <form>
        elements, which HTML doesn't allow and breaks CSRF."""
        return self.stripe_customer_link(obj)

    @admin.display(description='Aggrigator external ID', ordering='aggrigator_external_id')
    def aggrigator_external_id_display(self, obj):
        ext = obj.aggrigator_external_id
        if not ext:
            return '—'
        return _reveal(_mask_uuid(ext), str(ext))

    @admin.display(description='Aggrigator API key')
    def aggrigator_api_key_display(self, obj):
        key = obj.aggrigator_api_key
        if not key:
            return '—'
        # Short summary tells the operator length so they can spot a
        # truncated key without revealing the secret. The full value is
        # only on screen after they click Show.
        masked = f'{_mask_id(key)} ({len(key)} chars)'
        return _reveal(masked, key)
