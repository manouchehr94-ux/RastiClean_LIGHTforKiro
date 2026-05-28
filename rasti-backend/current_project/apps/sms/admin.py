from django.contrib import admin

from .models import SMSOutbox, SMSProvider


@admin.register(SMSProvider)
class SMSProviderAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "provider_type", "is_active"]
    list_filter = ["provider_type", "is_active", "company"]


@admin.register(SMSOutbox)
class SMSOutboxAdmin(admin.ModelAdmin):
    list_display = ["phone_number", "company", "status", "sent_at", "created_at"]
    list_filter = ["status", "company"]
