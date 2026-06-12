from django.contrib import admin

from core.metrics.models import ProductEvent


@admin.register(ProductEvent)
class ProductEventAdmin(admin.ModelAdmin):
    """Read-only event log — analysis happens in SQL / metrics_report."""

    list_display = ("created_at", "name", "user", "props")
    list_filter = ("name",)
    date_hierarchy = "created_at"
    search_fields = ("user__username", "user__email", "name")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
