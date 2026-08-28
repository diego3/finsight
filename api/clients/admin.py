from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "risk_profile", "created_at"]
    list_filter = ["risk_profile"]
    search_fields = ["name", "email"]
