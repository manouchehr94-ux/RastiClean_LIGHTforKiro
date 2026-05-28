"""
Reports - Models.

Report generation and caching for company dashboards.
"""
from django.db import models

from apps.common.models import CompanyOwnedModel


class Report(CompanyOwnedModel):
    """
    Generated report for a company.
    Stores report metadata and cached results.
    """

    class ReportType(models.TextChoices):
        ORDERS_SUMMARY = "orders_summary", "Orders Summary"
        REVENUE = "revenue", "Revenue Report"
        TECHNICIAN_PERFORMANCE = "technician_performance", "Technician Performance"
        CUSTOMER_ACTIVITY = "customer_activity", "Customer Activity"

    report_type = models.CharField(max_length=30, choices=ReportType.choices)
    title = models.CharField(max_length=200)
    parameters = models.JSONField(default=dict, blank=True)
    result_data = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.report_type})"
