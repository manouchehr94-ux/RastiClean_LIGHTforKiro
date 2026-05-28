from django.contrib import admin

from .models import (
    Company,
    CompanyGalleryImage,
    CompanyPage,
    CompanyService,
    CompanySettings,
    ServiceRequest,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active", "email", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "code", "email"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(CompanyPage)
class CompanyPageAdmin(admin.ModelAdmin):
    list_display = ["company", "is_published", "is_request_form_enabled", "updated_at"]
    list_filter = ["is_published", "is_request_form_enabled"]


@admin.register(CompanyService)
class CompanyServiceAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "base_price", "is_active"]
    list_filter = ["is_active", "company"]


@admin.register(CompanyGalleryImage)
class CompanyGalleryImageAdmin(admin.ModelAdmin):
    list_display = ["caption", "company", "sort_order", "is_active"]
    list_filter = ["is_active", "company"]


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ["customer_name", "customer_phone", "company", "service", "created_at"]
    list_filter = ["company"]
    search_fields = ["customer_name", "customer_phone"]



@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = [
        "company",
        "priority2_delay_minutes",
        "priority3_delay_minutes",
        "max_active_orders_per_technician",
        "auto_recycle_cancel_request",
    ]
    list_filter = ["auto_recycle_cancel_request", "show_future_orders_to_technicians"]
