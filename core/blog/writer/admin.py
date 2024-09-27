from django.contrib import admin

from .models import Tag, Article

@admin.register(Article)

class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'event', 'date_published', 'is_published')
    list_filter = ('is_published', 'author', 'event', 'tags')
    search_fields = ('title', 'content', 'author__username', 'event__title')  # Corrected field name
    # prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'date_published'
    ordering = ['-date_published']

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)