"""
Platform Core - URL Configuration.

These URLs are served under /loginlogin/ prefix.
Only accessible by PLATFORM_OWNER.
"""
from django.urls import path

from apps.accounts import views as auth_views

from . import views

app_name = "platform_core"

urlpatterns = [
    # Auth
    path("", auth_views.platform_login, name="login"),
    path("logout/", auth_views.platform_logout, name="logout"),

    # Dashboard + Reports
    path("dashboard/", views.platform_dashboard, name="dashboard"),
    path("reports/", views.platform_reports, name="reports"),

    # Company Management
    path("companies/", views.company_list, name="companies"),
    path("companies/create/", views.company_create, name="company_create"),
    path("companies/<int:company_id>/", views.company_detail, name="company_detail"),
    path("companies/<int:company_id>/edit/", views.company_edit, name="company_edit"),
    path("companies/<int:company_id>/activate/", views.company_activate, name="company_activate"),
    path("companies/<int:company_id>/deactivate/", views.company_deactivate, name="company_deactivate"),

    # Plan Management
    path("plans/", views.plan_list, name="plans"),
    path("plans/create/", views.plan_create, name="plan_create"),
    path("plans/<int:plan_id>/edit/", views.plan_edit, name="plan_edit"),

    # Subscription Management
    path("subscriptions/", views.subscription_list, name="subscriptions"),
    path("subscriptions/create/", views.subscription_create, name="subscription_create"),
    path("subscriptions/<int:subscription_id>/edit/", views.subscription_edit, name="subscription_edit"),
    path("subscriptions/<int:subscription_id>/activate/", views.subscription_activate, name="subscription_activate"),
    path("subscriptions/<int:subscription_id>/cancel/", views.subscription_cancel, name="subscription_cancel"),
]
