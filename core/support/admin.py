from django.contrib import admin
from .models import Category, Status, Ticket, Comment

admin.site.register(Category)
admin.site.register(Status)
admin.site.register(Ticket)
admin.site.register(Comment)