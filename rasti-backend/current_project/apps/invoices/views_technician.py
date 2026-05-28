"""
Invoices - Technician Views.

Read-only invoice views for technicians.
Technicians can only see invoices linked to their assigned orders.
"""
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import render

from apps.accounts.permissions import require_tenant_role

from .models import Invoice


@require_tenant_role("TECHNICIAN")
def technician_invoice_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """List invoices for orders assigned to the current technician."""
    company = request.company
    technician = getattr(request.user, "technician_profile", None)

    if not technician:
        return HttpResponseForbidden("Technician profile not found.")

    invoices_qs = Invoice.objects.filter(
        company=company,
        order__technician=technician,
    ).select_related("order").order_by("-created_at")

    # Optional filter by order
    order_filter = request.GET.get("order", "")
    if order_filter:
        try:
            invoices_qs = invoices_qs.filter(order_id=int(order_filter))
        except (ValueError, TypeError):
            pass

    # Optional filter by status
    status_filter = request.GET.get("status", "")
    if status_filter:
        invoices_qs = invoices_qs.filter(status=status_filter)

    return render(request, "orders/technician_invoices.html", {
        "invoices": invoices_qs[:50],
        "company": company,
        "order_filter": order_filter,
        "status_filter": status_filter,
        "statuses": Invoice.Status.choices,
    })


@require_tenant_role("TECHNICIAN")
def technician_invoice_detail(request: HttpRequest, invoice_id: int, **kwargs) -> HttpResponse:
    """View a single invoice detail (read-only) for technician's orders."""
    company = request.company
    technician = getattr(request.user, "technician_profile", None)

    if not technician:
        return HttpResponseForbidden("Technician profile not found.")

    invoice = Invoice.objects.filter(
        id=invoice_id,
        company=company,
        order__technician=technician,
    ).select_related("order").first()

    if invoice is None:
        raise Http404("Invoice not found.")

    return render(request, "orders/technician_invoice_detail.html", {
        "invoice": invoice,
        "company": company,
    })
