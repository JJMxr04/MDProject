# from django.contrib import admin
# from .models import Article, Tag

# @admin.register(Article)
# class ArticleAdmin(admin.ModelAdmin):
#     list_display = ('title', 'author', 'event', 'published_at', 'is_published')
#     list_filter = ('is_published', 'author', 'event', 'tags')
#     search_fields = ('title', 'content', 'author__username', 'event__title')  # Corrected field name
#     prepopulated_fields = {'slug': ('title',)}
#     date_hierarchy = 'published_at'
#     ordering = ['-published_at']

# @admin.register(Tag)
# class TagAdmin(admin.ModelAdmin):
#     list_display = ('name',)
#     search_fields = ('name',)
