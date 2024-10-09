from django.contrib import admin
from core.payments.models import Invoice

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('stripe_invoice_id', 'user', 'subscription', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('stripe_invoice_id', 'user__email', 'subscription__id')

