"""
Orders - Views.

Thin views that delegate all business logic to services/selectors.
Access control uses decorators and permission functions.

IMPORTANT: No business logic in views. Views only:
1. Validate request
2. Call services/selectors
3. Return response
"""
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import UserRole
from apps.accounts.permissions import require_tenant_auth, require_tenant_role

from . import permissions as order_perms
from .forms import OrderCreateForm
from .models import Order
from .selectors import OrderSelector
from .services import (
    OrderAcceptService,
    OrderCancelService,
    OrderCompleteService,
    OrderCreateService,
    TechnicianAcceptService,
)


@require_tenant_auth
def order_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    List orders based on user role.
    - Admin/Staff: all company orders
    - Technician: assigned orders + visible orders for acceptance
    - Customer: own orders only
    """
    user = request.user
    company = request.company

    if user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
        return redirect(f"/{company.code}/admin/orders/")
    elif user.role == UserRole.TECHNICIAN:
        return redirect(f"/{company.code}/tech/orders/my/")
    elif user.role == UserRole.CUSTOMER:
        customer = getattr(user, "customer_profile", None)
        if customer:
            orders = OrderSelector.get_for_customer(customer=customer)
        else:
            orders = Order.objects.none()
    else:
        orders = Order.objects.none()

    can_create_order = user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]

    return render(request, "orders/list.html", {
        "orders": orders,
        "company": company,
        "can_create_order": can_create_order,
    })


@require_tenant_auth
def order_detail(request: HttpRequest, order_id: int, **kwargs) -> HttpResponse:
    """View a single order. Permission checked via can_view_order."""
    company = request.company
    order = OrderSelector.get_by_id_for_company(order_id=order_id, company=company)

    if order is None:
        raise Http404("Order not found.")

    legacy_public_prefix = f"/{company.code}/orders/"
    if request.path.startswith(legacy_public_prefix):
        if request.user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
            return redirect(f"/{company.code}/admin/orders/{order.id}/")
        if request.user.role == UserRole.TECHNICIAN:
            return redirect(f"/{company.code}/tech/orders/{order.id}/")

    if not order_perms.can_view_order(user=request.user, order=order):
        return HttpResponseForbidden("Access denied.")

    from .item_services import OrderItemService
    from .selectors import OrderStatusLogSelector

    technician = getattr(request.user, "technician_profile", None)
    is_assigned_technician = bool(
        request.user.role == UserRole.TECHNICIAN
        and technician
        and order.technician_id == technician.id
    )

    return render(request, "orders/detail.html", {
        "order": order,
        "company": company,
        "item_values": OrderItemService.get_values_display(order=order),
        "status_logs": OrderStatusLogSelector.get_for_order(order=order)[:20],
        "is_assigned_technician": is_assigned_technician,
        "can_accept": order_perms.can_accept_order(user=request.user, order=order),
        "can_complete": order_perms.can_complete_order(user=request.user, order=order),
        "can_cancel": order_perms.can_cancel_order(user=request.user, order=order),
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def order_create(request: HttpRequest, **kwargs) -> HttpResponse:
    """Create a new order. Only admin/staff can create."""
    company = request.company
    error = ""

    if request.method == "POST":
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            from apps.accounts.models import Customer
            customer = Customer.objects.filter(
                id=form.cleaned_data["customer_id"],
                company=company,
            ).first()

            if not customer:
                error = "Customer not found."
            else:
                try:
                    order = OrderCreateService.create(
                        company=company,
                        customer=customer,
                        title=form.cleaned_data["title"],
                        description=form.cleaned_data.get("description", ""),
                        address=form.cleaned_data.get("address", ""),
                        priority=form.cleaned_data["priority"],
                        price_estimate=form.cleaned_data.get("price_estimate") or 0,
                        required_skill=form.cleaned_data.get("required_skill", ""),
                        created_by=request.user,
                    )
                    return redirect(f"/{company.code}/admin/orders/{order.id}/")
                except ValueError as e:
                    error = str(e)
    else:
        form = OrderCreateForm()

    # Get customers for the company (for selection)
    from apps.accounts.models import Customer
    customers = Customer.objects.filter(company=company)

    return render(request, "orders/create.html", {
        "form": form,
        "company": company,
        "customers": customers,
        "error": error,
    })


@require_tenant_auth
def order_accept(request: HttpRequest, order_id: int, **kwargs) -> HttpResponse:
    """Technician accepts an order."""
    company = request.company
    order = OrderSelector.get_by_id_for_company(order_id=order_id, company=company)

    if order is None:
        raise Http404("Order not found.")

    if not order_perms.can_accept_order(user=request.user, order=order):
        return HttpResponseForbidden("Cannot accept this order.")

    if request.method == "POST":
        technician = getattr(request.user, "technician_profile", None)
        if not technician:
            return HttpResponseForbidden("Technician profile not found.")

        try:
            # Use new category-based accept if order has service_category
            if order.service_category_id is not None:
                TechnicianAcceptService.accept(
                    order=order,
                    technician=technician,
                    accepted_by=request.user,
                )
            else:
                # Fallback to legacy skill-based accept
                OrderAcceptService.accept(
                    order=order,
                    technician=technician,
                    accepted_by=request.user,
                )
            return redirect(f"/{company.code}/tech/orders/{order.id}/")
        except ValueError as e:
            return render(request, "orders/detail.html", {
                "order": order,
                "company": company,
                "error": str(e),
            })

    return redirect(f"/{company.code}/tech/orders/{order.id}/")


@require_tenant_auth
def order_complete(request: HttpRequest, order_id: int, **kwargs) -> HttpResponse:
    """Mark an order as complete."""
    company = request.company
    order = OrderSelector.get_by_id_for_company(order_id=order_id, company=company)

    if order is None:
        raise Http404("Order not found.")

    if not order_perms.can_complete_order(user=request.user, order=order):
        return HttpResponseForbidden("Cannot complete this order.")

    if request.method == "POST":
        final_price = request.POST.get("final_price")
        try:
            OrderCompleteService.complete(
                order=order,
                completed_by=request.user,
                final_price=int(final_price) if final_price else None,
            )
            return redirect(f"/{company.code}/tech/orders/{order.id}/")
        except ValueError as e:
            return render(request, "orders/detail.html", {
                "order": order,
                "company": company,
                "error": str(e),
            })

    return redirect(f"/{company.code}/tech/orders/{order.id}/")


@require_tenant_auth
def order_cancel(request: HttpRequest, order_id: int, **kwargs) -> HttpResponse:
    """Cancel or request cancellation of an order."""
    company = request.company
    order = OrderSelector.get_by_id_for_company(order_id=order_id, company=company)

    if order is None:
        raise Http404("Order not found.")

    if not order_perms.can_cancel_order(user=request.user, order=order):
        return HttpResponseForbidden("Cannot cancel this order.")

    if request.method == "POST":
        reason = request.POST.get("reason", "")

        try:
            # Admin/Staff can force cancel
            if request.user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
                OrderCancelService.force_cancel(
                    order=order,
                    cancelled_by=request.user,
                    reason=reason,
                )
            else:
                # Technician/Customer can only request cancellation
                OrderCancelService.request_cancel(
                    order=order,
                    requested_by=request.user,
                    reason=reason,
                )
            return redirect(f"/{company.code}/tech/orders/{order.id}/")
        except ValueError as e:
            return render(request, "orders/detail.html", {
                "order": order,
                "company": company,
                "error": str(e),
            })

    return redirect(f"/{company.code}/tech/orders/{order.id}/")


@require_tenant_role("TECHNICIAN")
def technician_available_orders(request: HttpRequest, **kwargs) -> HttpResponse:
    """List orders available for a technician to accept (category-based)."""
    from .item_services import OrderItemService
    from .selectors import TechnicianOrderVisibilitySelector

    company = request.company
    technician = getattr(request.user, "technician_profile", None)

    if not technician:
        return HttpResponseForbidden("Technician profile not found.")

    orders = TechnicianOrderVisibilitySelector.get_available_orders(
        technician=technician,
    )

    # Attach item values and accept state to each order for display.
    # Future orders may be visible but not acceptable until the service date gate.
    orders_with_items = []
    for order in orders:
        accept_allowed = order_perms.can_accept_order(user=request.user, order=order)
        orders_with_items.append({
            "order": order,
            "item_values": OrderItemService.get_values_display(order=order),
            "accept_allowed": accept_allowed,
            "accept_block_reason": "در تاریخ مقرر و بعد از ساعت مجاز قابل قبول کردن است." if not accept_allowed else "",
        })

    return render(request, "orders/technician_available.html", {
        "orders_with_items": orders_with_items,
        "company": company,
    })


@require_tenant_role("TECHNICIAN")
def technician_my_orders(request: HttpRequest, **kwargs) -> HttpResponse:
    """List orders assigned to the current technician."""
    from .item_services import OrderItemService

    company = request.company
    technician = getattr(request.user, "technician_profile", None)

    if not technician:
        return HttpResponseForbidden("Technician profile not found.")

    status_filter = request.GET.get("status", "")
    orders_qs = Order.objects.filter(
        company=company, technician=technician,
    ).order_by("-created_at")

    if status_filter:
        orders_qs = orders_qs.filter(status=status_filter)

    orders_with_items = []
    for order in orders_qs[:50]:
        orders_with_items.append({
            "order": order,
            "item_values": OrderItemService.get_values_display(order=order),
        })

    return render(request, "orders/technician_my_orders.html", {
        "orders_with_items": orders_with_items,
        "company": company,
        "status_filter": status_filter,
        "statuses": Order.Status.choices,
    })


@require_tenant_role("TECHNICIAN")
def technician_status_update(request: HttpRequest, order_id: int, **kwargs) -> HttpResponse:
    """Technician updates the status of their own assigned order."""
    from .services import TechnicianStatusUpdateService

    company = request.company
    technician = getattr(request.user, "technician_profile", None)

    if not technician:
        return HttpResponseForbidden("Technician profile not found.")

    order = OrderSelector.get_by_id_for_company(order_id=order_id, company=company)
    if order is None:
        raise Http404("Order not found.")

    if request.method == "POST":
        new_status = request.POST.get("new_status", "")
        note = request.POST.get("note", "")
        try:
            TechnicianStatusUpdateService.update_status(
                order=order,
                technician=technician,
                new_status=new_status,
                updated_by=request.user,
                note=note,
            )
            return redirect(f"/{company.code}/tech/orders/my/")
        except ValueError as e:
            return render(request, "orders/detail.html", {
                "order": order,
                "company": company,
                "error": str(e),
            })

    return redirect(f"/{company.code}/tech/orders/{order.id}/")



@require_tenant_role("TECHNICIAN")
def technician_invoices(request: HttpRequest, **kwargs) -> HttpResponse:
    """List invoices for orders assigned to this technician."""
    company = request.company
    technician = getattr(request.user, "technician_profile", None)

    if not technician:
        return HttpResponseForbidden("Technician profile not found.")

    from django.db.models import Sum, Q
    from apps.invoices.models import Invoice, InvoiceItem

    invoices = Invoice.objects.filter(
        company=company,
        order__technician=technician,
    ).order_by("-created_at")[:50]

    # Summary calculations
    all_invoices_qs = Invoice.objects.filter(
        company=company,
        order__technician=technician,
    )
    invoice_count = all_invoices_qs.count()
    total_amount = all_invoices_qs.aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    # Service vs travel fee breakdown
    items_qs = InvoiceItem.objects.filter(
        invoice__company=company,
        invoice__order__technician=technician,
    )
    travel_total = items_qs.filter(
        description__contains="\u0627\u06cc\u0627\u0628 \u0648 \u0630\u0647\u0627\u0628"
    ).aggregate(total=Sum("total_price"))["total"] or 0
    service_total = items_qs.exclude(
        description__contains="\u0627\u06cc\u0627\u0628 \u0648 \u0630\u0647\u0627\u0628"
    ).aggregate(total=Sum("total_price"))["total"] or 0

    summary = {
        "invoice_count": invoice_count,
        "total_amount": total_amount,
        "service_total": service_total,
        "travel_total": travel_total,
    }

    return render(request, "orders/technician_invoices.html", {
        "company": company,
        "invoices": invoices,
        "summary": summary,
    })
