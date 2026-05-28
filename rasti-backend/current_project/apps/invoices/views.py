"""
Invoices - Views.

Thin views for invoice display and payment.
Business logic delegated to services/selectors.
"""
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render

from apps.accounts.models import UserRole
from apps.accounts.permissions import require_tenant_auth

from .models import Invoice
from .selectors import InvoiceSelector


@require_tenant_auth
def invoice_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    List invoices based on user role.
    - Admin/Staff: all company invoices
    - Customer: own invoices only
    """
    user = request.user
    company = request.company

    if user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
        invoices = InvoiceSelector.get_for_company(company=company)
    elif user.role == UserRole.CUSTOMER:
        customer = getattr(user, "customer_profile", None)
        if customer:
            invoices = InvoiceSelector.get_for_customer(customer=customer)
        else:
            invoices = Invoice.objects.none()
    else:
        invoices = Invoice.objects.none()

    return render(request, "invoices/list.html", {
        "invoices": invoices,
        "company": company,
    })


@require_tenant_auth
def invoice_detail(request: HttpRequest, invoice_id: int, **kwargs) -> HttpResponse:
    """View a single invoice."""
    company = request.company
    invoice = InvoiceSelector.get_by_id_for_company(
        invoice_id=invoice_id, company=company
    )

    if invoice is None:
        raise Http404("Invoice not found.")

    user = request.user
    if user.role == UserRole.CUSTOMER:
        customer = getattr(user, "customer_profile", None)
        if not customer or invoice.customer_id != customer.id:
            return HttpResponseForbidden("Access denied.")

    return render(request, "invoices/detail.html", {
        "invoice": invoice,
        "company": company,
    })


def public_invoice_detail(request: HttpRequest, public_code: str, **kwargs) -> HttpResponse:
    """Read-only public invoice view by short public code."""
    company = request.company
    invoice = InvoiceSelector.get_by_public_code_for_company(
        company=company, public_code=public_code,
    )
    if invoice is None:
        raise Http404("Invoice not found.")
    if invoice.status == Invoice.Status.CANCELLED:
        raise Http404("Invoice not found.")
    return render(request, "invoices/public_detail.html", {
        "invoice": invoice,
        "company": company,
    })


def invoice_print(request: HttpRequest, public_code: str, **kwargs) -> HttpResponse:
    """
    Invoice print/download page (Phase 27A) — public access via public_code.

    Renders a clean, print-optimized HTML page for the invoice.
    Browser print dialog or "Save as PDF" produces a production-quality document.

    Uses the invoice public_code (not numeric ID) in the URL for safety.

    Access rules match public_invoice_detail:
    - Anyone with the public_code link can view (same as public detail).
    - DRAFT and CANCELLED invoices are not available.
    """
    company = request.company
    invoice = InvoiceSelector.get_by_public_code_for_company(
        company=company, public_code=public_code,
    )

    if invoice is None:
        raise Http404("Invoice not found.")

    # Block CANCELLED invoices only (consistent with public_invoice_detail)
    if invoice.status == Invoice.Status.CANCELLED:
        raise Http404("Invoice not found.")

    return render(request, "invoices/print.html", {
        "invoice": invoice,
        "company": company,
    })


@require_tenant_auth
def invoice_pay(request: HttpRequest, invoice_id: int, **kwargs) -> HttpResponse:
    """
    Start payment for an invoice.
    Redirects to payment gateway.
    """
    company = request.company
    invoice = InvoiceSelector.get_by_id_for_company(
        invoice_id=invoice_id, company=company
    )

    if invoice is None:
        raise Http404("Invoice not found.")

    if not invoice.is_payable:
        return render(request, "payments/result.html", {
            "success": False,
            "message": "This invoice is not payable.",
            "company": company,
        })

    from apps.payments.services import PaymentStartService

    callback_url = request.build_absolute_uri(
        f"/{company.code}/payments/callback/"
    )

    try:
        payment, attempt, redirect_url = PaymentStartService.start(
            invoice=invoice,
            callback_url=callback_url,
        )
    except ValueError as e:
        return render(request, "payments/result.html", {
            "success": False,
            "message": str(e),
            "company": company,
        })

    if redirect_url:
        return redirect(redirect_url)
    else:
        return render(request, "payments/result.html", {
            "success": False,
            "message": "Failed to initiate payment. Please try again.",
            "company": company,
        })
