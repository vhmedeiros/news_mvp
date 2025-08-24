from django.contrib import admin
from .models import Vehicle, Section

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("name", "media_type", "status", "country", "state", "city", "url", "created_at", "updated_at")
    list_filter = ("media_type", "status", "country", "state", "city")
    search_fields = ("name", "url", "country", "state", "city", "notes")

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name", "vehicle")
    list_filter = ("vehicle",)
    search_fields = ("name", "vehicle__name")
