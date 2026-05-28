from django.contrib import admin

from .models import Notification, NotificationSetting


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "recipient", "notification_type", "is_read"]
    list_filter = ["notification_type", "is_read", "company"]



@admin.register(NotificationSetting)
class NotificationSettingAdmin(admin.ModelAdmin):
    list_display = ["company", "event_key", "in_app_enabled", "sms_enabled"]
    list_filter = ["event_key", "in_app_enabled", "sms_enabled", "company"]
