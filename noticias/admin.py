from django.contrib import admin
from .models import News

@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ("title", "vehicle", "section", "published_at", "captured_at")
    list_filter = ("vehicle", "section", "published_at", "captured_at")
    search_fields = ("title", "subtitle", "author", "url", "content")
