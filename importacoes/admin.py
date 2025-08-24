from django.contrib import admin
from .models import ImportConfig, ImportJob

@admin.register(ImportConfig)
class ImportConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "vehicle", "status", "enabled", "interval_minutes", "last_run_at")
    list_filter = ("status", "enabled", "vehicle")
    search_fields = ("name", "vehicle__name")

@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "config", "status", "started_at", "finished_at", "found_count", "new_count")
    list_filter = ("status", "config__vehicle")
