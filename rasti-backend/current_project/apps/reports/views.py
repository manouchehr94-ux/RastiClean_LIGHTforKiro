"""
Reports - Views.

Company-level reports for admin/staff.
All query logic is in selectors.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.accounts.permissions import require_tenant_role

from .selectors import CompanyReportSelector


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def report_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """Company reports overview."""
    company = request.company

    order_summary = CompanyReportSelector.order_summary(company=company)
    revenue_summary = CompanyReportSelector.revenue_summary(company=company)
    invoice_summary = CompanyReportSelector.invoice_summary(company=company)
    technician_perf = CompanyReportSelector.technician_performance(company=company)
    request_summary = CompanyReportSelector.service_request_summary(company=company)

    return render(request, "reports/list.html", {
        "company": company,
        "order_summary": order_summary,
        "revenue_summary": revenue_summary,
        "invoice_summary": invoice_summary,
        "technician_performance": technician_perf,
        "request_summary": request_summary,
    })
