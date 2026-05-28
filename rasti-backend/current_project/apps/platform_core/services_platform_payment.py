"""
Platform Payment Service — Mock/Dev payment flow.
No real gateway calls. Architecture ready for future Zarinpal/Zibal/IDPay.
"""
import uuid
from django.db import transaction
from django.utils import timezone
from .models import PlatformBillingInvoice, PlatformPaymentTransaction, PaymentGatewayProvider
from .services_sms_credit import SMSCreditService


class PlatformPaymentService:
    """Handles platform invoice payment flow (mock for now)."""

    @staticmethod
    def start_platform_invoice_payment(invoice, company, user=None):
        """Create a payment transaction for an unpaid invoice."""
        if invoice.status == PlatformBillingInvoice.Status.PAID:
            return None  # Already paid

        # Check if there's already an active (non-failed) transaction
        existing = PlatformPaymentTransaction.objects.filter(
            invoice=invoice,
            status__in=[
                PlatformPaymentTransaction.Status.INITIATED,
                PlatformPaymentTransaction.Status.VERIFIED,
                PlatformPaymentTransaction.Status.PAID,
            ]
        ).first()
        if existing and existing.status in ['VERIFIED', 'PAID']:
            return None  # Already verified

        txn = PlatformPaymentTransaction.objects.create(
            invoice=invoice,
            company=company,
            amount_rial=invoice.amount_rial,
            provider=PaymentGatewayProvider.MOCK,
            status=PlatformPaymentTransaction.Status.INITIATED,
            authority=f"MOCK-{uuid.uuid4().hex[:12].upper()}",
        )
        return txn

    @staticmethod
    @transaction.atomic
    def process_mock_success(txn, user=None):
        """Process a successful mock payment. Anti-double-credit protected."""
        # Guard: already verified
        if txn.status in ['VERIFIED', 'PAID']:
            return txn

        # Guard: invoice already paid
        invoice = txn.invoice
        if invoice.status == PlatformBillingInvoice.Status.PAID:
            txn.status = PlatformPaymentTransaction.Status.VERIFIED
            txn.verified_at = timezone.now()
            txn.tracking_code = f"MOCK-TRK-{uuid.uuid4().hex[:8].upper()}"
            txn.save(update_fields=['status', 'verified_at', 'tracking_code'])
            return txn

        # Mark transaction verified
        txn.status = PlatformPaymentTransaction.Status.VERIFIED
        txn.verified_at = timezone.now()
        txn.reference_id = f"MOCK-REF-{uuid.uuid4().hex[:8].upper()}"
        txn.tracking_code = f"MOCK-TRK-{uuid.uuid4().hex[:8].upper()}"
        txn.save(update_fields=['status', 'verified_at', 'reference_id', 'tracking_code'])

        # Mark invoice paid + credit wallet
        SMSCreditService.mark_invoice_paid(invoice, paid_by=user)

        return txn

    @staticmethod
    def process_mock_failure(txn, reason="پرداخت ناموفق آزمایشی"):
        """Process a failed mock payment."""
        if txn.status in ['VERIFIED', 'PAID']:
            return txn  # Can't fail an already verified transaction

        txn.status = PlatformPaymentTransaction.Status.FAILED
        txn.gateway_response = reason
        txn.save(update_fields=['status', 'gateway_response'])
        return txn

    @staticmethod
    def get_invoice_payment_transactions(invoice):
        """Get all payment transactions for an invoice."""
        return PlatformPaymentTransaction.objects.filter(invoice=invoice).order_by('-created_at')
