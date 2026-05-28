"""
Payments - Selectors.

All read operations for payments. ALWAYS company-scoped.
"""
from typing import Optional

from django.db.models import QuerySet

from .models import Payment, PaymentAttempt, PaymentGateway


class PaymentSelector:
    """Read operations for Payment records."""

    @staticmethod
    def get_for_company(*, company) -> QuerySet[Payment]:
        """Get all payments for a company."""
        return Payment.objects.filter(company=company)

    @staticmethod
    def get_for_invoice(*, company, invoice_id: int) -> QuerySet[Payment]:
        """Get payments for a specific invoice."""
        return Payment.objects.filter(company=company, invoice_id=invoice_id)

    @staticmethod
    def get_by_id_for_company(*, payment_id: int, company) -> Optional[Payment]:
        """Get a single payment by ID, company-scoped."""
        return Payment.objects.filter(id=payment_id, company=company).first()

    @staticmethod
    def get_by_reference(*, company, reference_id: str) -> Optional[Payment]:
        """Get payment by gateway reference ID."""
        return Payment.objects.filter(
            company=company, reference_id=reference_id
        ).first()

    @staticmethod
    def get_successful_for_company(*, company) -> QuerySet[Payment]:
        """Get all successful payments."""
        return Payment.objects.filter(company=company, status=Payment.Status.PAID)


class PaymentGatewaySelector:
    """Read operations for PaymentGateway."""

    @staticmethod
    def get_active_for_company(*, company) -> QuerySet[PaymentGateway]:
        """Get active gateways for a company."""
        return PaymentGateway.objects.filter(company=company, is_active=True)

    @staticmethod
    def get_default_for_company(*, company) -> Optional[PaymentGateway]:
        """Get the default active gateway for a company."""
        return PaymentGateway.objects.filter(
            company=company, is_active=True, is_default=True
        ).first()

    @staticmethod
    def get_by_type(*, company, gateway_type: str) -> Optional[PaymentGateway]:
        """Get gateway by type for a company."""
        return PaymentGateway.objects.filter(
            company=company, gateway_type=gateway_type
        ).first()
