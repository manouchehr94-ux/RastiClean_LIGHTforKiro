"""SMS - URLs. Served under /<company_code>/admin/sms/"""
from django.urls import path

from . import views

app_name = "sms"

urlpatterns = [
    # Legacy outbox view (kept for backward compat, redirects or shows simple list)
    path("", views.sms_outbox_list, name="outbox"),

    # SMS Template management (Phase 26)
    path("templates/", views.sms_template_list, name="template_list"),
    path("templates/create/", views.sms_template_create, name="template_create"),
    path("templates/<int:pk>/edit/", views.sms_template_edit, name="template_edit"),
    path("templates/<int:pk>/toggle/", views.sms_template_toggle, name="template_toggle"),

    # SMS Outbox management (Phase 26B)
    path("outbox/", views.sms_outbox_admin_list, name="outbox_list"),
    path("outbox/<int:pk>/send-now/", views.sms_outbox_send_now, name="outbox_send_now"),
    path("outbox/bulk-retry/", views.sms_outbox_bulk_retry, name="outbox_bulk_retry"),

    # SMS Diagnostics (Phase 26D)
    path("diagnostics/", views.sms_diagnostics, name="diagnostics"),
]
