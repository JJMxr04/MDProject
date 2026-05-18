from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

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
        """Detail-page version of stripe_customer_link — same renderer."""
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
