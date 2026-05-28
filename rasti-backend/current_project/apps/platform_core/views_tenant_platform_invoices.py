"""Tenant views for platform invoice listing and mock payment."""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from apps.accounts.permissions import require_tenant_role
from .models import PlatformBillingInvoice, PlatformPaymentTransaction
from .services_platform_payment import PlatformPaymentService


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_platform_invoices(request: HttpRequest, **kwargs) -> HttpResponse:
    """List platform invoices for this company."""
    company = request.company
    invoices = PlatformBillingInvoice.objects.filter(company=company).order_by('-created_at')[:50]
    return render(request, "tenants/admin_platform_invoices.html", {
        "company": company, "invoices": invoices,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_platform_invoice_detail(request: HttpRequest, invoice_id: int, **kwargs) -> HttpResponse:
    """Show platform invoice detail with pay button."""
    company = request.company
    invoice = get_object_or_404(PlatformBillingInvoice, id=invoice_id, company=company)
    transactions = PlatformPaymentService.get_invoice_payment_transactions(invoice)
    return render(request, "tenants/admin_platform_invoice_detail.html", {
        "company": company, "invoice": invoice, "transactions": transactions,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_platform_invoice_pay(request: HttpRequest, invoice_id: int, **kwargs) -> HttpResponse:
    """Start mock payment for an unpaid platform invoice."""
    company = request.company
    invoice = get_object_or_404(PlatformBillingInvoice, id=invoice_id, company=company)

    if request.method != "POST":
        return redirect("tenants:admin_platform_invoice_detail", invoice_id=invoice.id)

    if invoice.status == PlatformBillingInvoice.Status.PAID:
        return redirect("tenants:admin_platform_invoice_detail", invoice_id=invoice.id)

    txn = PlatformPaymentService.start_platform_invoice_payment(invoice, company, request.user)
    if txn is None:
        return redirect("tenants:admin_platform_invoice_detail", invoice_id=invoice.id)

    return redirect("tenants:admin_platform_invoice_mock", transaction_id=txn.id)


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_platform_invoice_mock(request: HttpRequest, transaction_id: int, **kwargs) -> HttpResponse:
    """Mock payment gateway page — success or failure buttons."""
    company = request.company
    txn = get_object_or_404(PlatformPaymentTransaction, id=transaction_id, company=company)

    if txn.status in ['VERIFIED', 'PAID']:
        return redirect("tenants:admin_platform_invoice_detail", invoice_id=txn.invoice_id)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "success":
            PlatformPaymentService.process_mock_success(txn, user=request.user)
            return redirect("tenants:admin_platform_invoice_detail", invoice_id=txn.invoice_id)
        elif action == "failure":
            PlatformPaymentService.process_mock_failure(txn)
            return redirect("tenants:admin_platform_invoice_detail", invoice_id=txn.invoice_id)

    return render(request, "tenants/admin_platform_invoice_mock.html", {
        "company": company, "txn": txn,
    })
