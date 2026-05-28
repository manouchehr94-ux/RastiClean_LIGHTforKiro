"""
Invoices - Service Layer.

All write operations for invoices.
Business logic MUST live here, never in views.
"""
from decimal import Decimal
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Customer

from .models import Invoice, InvoiceItem, generate_invoice_number


def _money(value, default=0) -> Decimal:
    if value in (None, ""):
        return Decimal(default)
    try:
        return Decimal(str(value).replace(",", "").strip() or default)
    except Exception:
        return Decimal(default)


def build_invoice_snapshot_from_order(order) -> dict[str, Any]:
    technician = order.technician
    technician_user = technician.user if technician else None
    return {
        "customer_name_snapshot": order.display_customer_name,
        "customer_phone_snapshot": order.display_customer_phone,
        "address_snapshot": order.address or "",
        "technician_name_snapshot": technician_user.get_full_name() if technician_user else "",
        "technician_phone_snapshot": technician_user.phone if technician_user else "",
        "service_title_snapshot": str(order.service_category or order.title or ""),
        "service_date_snapshot": order.service_date,
    }


class InvoiceCreateService:
    """
    Service for creating invoices.

    Rules:
    - Invoice must belong to a company
    - Customer, if present, must belong to the same company
    - Invoice number is auto-generated per company
    - Initial status is DRAFT
    """

    @staticmethod
    @transaction.atomic
    def create(
        *,
        company,
        customer: Customer | None = None,
        order=None,
        items: Optional[list[dict[str, Any]]] = None,
        notes: str = "",
        tax_amount=0,
        discount_amount=0,
        created_by=None,
        footer_text: str = "",
        **snapshots,
    ) -> Invoice:
        if customer and customer.company_id != company.id:
            raise ValueError("Customer does not belong to this company.")

        invoice = Invoice(
            company=company,
            customer=customer,
            order=order,
            created_by=created_by,
            invoice_number=generate_invoice_number(company),
            status=Invoice.Status.DRAFT,
            tax_amount=_money(tax_amount),
            discount_amount=_money(discount_amount),
            notes=notes or "",
            footer_text=footer_text or Invoice._meta.get_field("footer_text").default,
            **snapshots,
        )
        invoice.save()

        InvoiceItemBulkService.replace_items(invoice=invoice, items=items or [])
        invoice.recalculate_totals(save=True)
        return invoice

    @staticmethod
    @transaction.atomic
    def create_from_order(*, order, created_by=None) -> Invoice:
        """
        Create a draft invoice from an order.
        The order is operational; prices are entered on the invoice afterwards.
        """
        snapshots = build_invoice_snapshot_from_order(order)
        invoice = InvoiceCreateService.create(
            company=order.company,
            customer=order.customer,
            order=order,
            created_by=created_by,
            items=[],
            **snapshots,
        )
        return invoice


class InvoiceUpdateService:
    """Update draft invoice header + line items."""

    @staticmethod
    @transaction.atomic
    def update(
        *,
        invoice: Invoice,
        data: dict[str, Any],
        items: list[dict[str, Any]],
    ) -> Invoice:
        if invoice.status != Invoice.Status.DRAFT:
            raise ValueError("Only draft invoices can be edited.")

        # Snapshot/header fields are intentionally immutable after invoice creation.
        # They represent the exact order/customer/technician data at the time the
        # invoice draft was generated and must not be changed from the edit form.
        invoice.tax_amount = _money(data.get("tax_amount"))
        invoice.discount_amount = _money(data.get("discount_amount"))
        invoice.save()

        InvoiceItemBulkService.replace_items(invoice=invoice, items=items)
        invoice.recalculate_totals(save=True)
        return invoice


class InvoiceItemBulkService:
    """Replace invoice rows from a simple POST-style payload."""

    @staticmethod
    @transaction.atomic
    def replace_items(*, invoice: Invoice, items: list[dict[str, Any]]) -> None:
        InvoiceItem.objects.filter(company=invoice.company, invoice=invoice).delete()
        rows = []
        for idx, item in enumerate(items):
            description = (item.get("description") or "").strip()
            if not description:
                continue
            quantity = _money(item.get("quantity"), default=1)
            if quantity <= 0:
                quantity = Decimal("1")
            unit_price = _money(item.get("unit_price"))
            discount = _money(item.get("discount_amount"))
            rows.append(
                InvoiceItem(
                    company=invoice.company,
                    invoice=invoice,
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    discount_amount=discount,
                    total_price=max(0, quantity * unit_price - discount),
                    sort_order=idx,
                )
            )
        if rows:
            InvoiceItem.objects.bulk_create(rows)


class InvoiceIssueService:
    """Service for issuing invoices (DRAFT → ISSUED)."""

    @staticmethod
    @transaction.atomic
    def issue(*, invoice: Invoice) -> Invoice:
        if invoice.status != Invoice.Status.DRAFT:
            raise ValueError("Only draft invoices can be issued.")

        invoice.recalculate_totals(save=True)
        if invoice.total_amount <= 0:
            raise ValueError("Cannot issue invoice with zero or negative amount.")

        invoice.status = Invoice.Status.ISSUED
        invoice.issued_at = timezone.now()
        invoice.save(update_fields=["status", "issued_at", "updated_at"])
        return invoice


class InvoiceCancelService:
    """Service for cancelling invoices."""

    @staticmethod
    @transaction.atomic
    def cancel(*, invoice: Invoice, reason: str = "") -> Invoice:
        if invoice.status not in [Invoice.Status.DRAFT, Invoice.Status.ISSUED]:
            raise ValueError("Only draft or issued invoices can be cancelled.")

        invoice.status = Invoice.Status.CANCELLED
        if reason:
            invoice.notes = f"{invoice.notes}\nلغو: {reason}".strip()
        invoice.save(update_fields=["status", "notes", "updated_at"])
        return invoice


class InvoiceMarkPaidService:
    """Mark issued invoices as paid."""

    @staticmethod
    @transaction.atomic
    def mark_paid(*, invoice: Invoice) -> Invoice:
        if invoice.status != Invoice.Status.ISSUED:
            raise ValueError("Only issued invoices can be marked as paid.")

        invoice.status = Invoice.Status.PAID
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=["status", "paid_at", "updated_at"])
        return invoice
