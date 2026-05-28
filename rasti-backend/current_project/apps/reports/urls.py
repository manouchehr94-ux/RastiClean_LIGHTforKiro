"""Reports - URLs. Served under /<company_code>/reports/"""
from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_list, name="list"),
]
