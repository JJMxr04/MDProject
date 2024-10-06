from django.contrib import admin

from .models import Tag, Article, SubscriptionPlan  # Added SubscriptionPlan

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'event', 'date_published', 'is_published')
    list_filter = ('is_published', 'author', 'event', 'tags')
    search_fields = ('title', 'content', 'author__username', 'event__title')  # Corrected field name
    date_hierarchy = 'date_published'
    ordering = ['-date_published']

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(SubscriptionPlan)  # Registering SubscriptionPlan
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('writer', 'price')  # Added writer to the display
    search_fields = ('writer__username',)  # Allow searching by writer's username