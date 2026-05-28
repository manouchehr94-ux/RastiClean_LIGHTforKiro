"""SMS Credit Wallet Service. No real SMS provider — accounting only."""
import math
import uuid
from django.db import transaction
from django.utils import timezone
from .models import GlobalSMSPricingSetting, CompanySMSWallet, CompanySMSTransaction, PlatformBillingInvoice


class SMSCreditService:
    @staticmethod
    def get_pricing():
        pricing, _ = GlobalSMSPricingSetting.objects.get_or_create(pk=1)
        return pricing

    @staticmethod
    def get_or_create_wallet(company):
        wallet, _ = CompanySMSWallet.objects.get_or_create(company=company)
        return wallet

    @staticmethod
    def estimate_sms_parts(message_text: str) -> int:
        pricing = SMSCreditService.get_pricing()
        length = len(message_text or "")
        if length == 0:
            return 0
        return math.ceil(length / pricing.characters_per_sms)

    @staticmethod
    def estimate_message_cost(message_text: str) -> int:
        parts = SMSCreditService.estimate_sms_parts(message_text)
        pricing = SMSCreditService.get_pricing()
        return parts * pricing.price_per_sms_rial

    @staticmethod
    def get_remaining_sms_count(company) -> int:
        wallet = SMSCreditService.get_or_create_wallet(company)
        pricing = SMSCreditService.get_pricing()
        if pricing.price_per_sms_rial <= 0:
            return 0
        return wallet.balance_rial // pricing.price_per_sms_rial

    @staticmethod
    def has_sufficient_credit(company, message_text: str) -> bool:
        cost = SMSCreditService.estimate_message_cost(message_text)
        wallet = SMSCreditService.get_or_create_wallet(company)
        return wallet.balance_rial >= cost

    @staticmethod
    @transaction.atomic
    def debit_for_sms(company, message_text: str, description: str = "") -> CompanySMSTransaction:
        cost = SMSCreditService.estimate_message_cost(message_text)
        parts = SMSCreditService.estimate_sms_parts(message_text)
        wallet = SMSCreditService.get_or_create_wallet(company)

        if wallet.balance_rial < cost:
            # Insufficient — record BLOCKED transaction
            return CompanySMSTransaction.objects.create(
                company=company, wallet=wallet,
                transaction_type=CompanySMSTransaction.TransactionType.BLOCKED,
                amount_rial=cost, sms_parts=parts, message_length=len(message_text or ""),
                balance_after=wallet.balance_rial,
                description=description or "اعتبار ناکافی",
            )

        wallet.balance_rial -= cost
        wallet.save(update_fields=["balance_rial", "updated_at"])

        return CompanySMSTransaction.objects.create(
            company=company, wallet=wallet,
            transaction_type=CompanySMSTransaction.TransactionType.DEBIT,
            amount_rial=cost, sms_parts=parts, message_length=len(message_text or ""),
            balance_after=wallet.balance_rial,
            description=description or f"مصرف {parts} پیامک",
        )

    @staticmethod
    @transaction.atomic
    def credit_wallet(company, amount_rial: int, invoice=None, created_by=None) -> CompanySMSTransaction:
        wallet = SMSCreditService.get_or_create_wallet(company)
        wallet.balance_rial += amount_rial
        wallet.save(update_fields=["balance_rial", "updated_at"])

        return CompanySMSTransaction.objects.create(
            company=company, wallet=wallet,
            transaction_type=CompanySMSTransaction.TransactionType.CREDIT,
            amount_rial=amount_rial, balance_after=wallet.balance_rial,
            description=f"شارژ {amount_rial:,} ریال",
            related_invoice=invoice, created_by=created_by,
        )

    @staticmethod
    def create_recharge_invoice(company, amount_rial: int, created_by=None) -> PlatformBillingInvoice:
        inv_number = f"SMS-{uuid.uuid4().hex[:8].upper()}"
        return PlatformBillingInvoice.objects.create(
            company=company, invoice_number=inv_number,
            invoice_type=PlatformBillingInvoice.InvoiceType.SMS_RECHARGE,
            amount_rial=amount_rial, status=PlatformBillingInvoice.Status.UNPAID,
            description=f"شارژ پیامک - {amount_rial:,} ریال",
            created_by=created_by,
        )

    @staticmethod
    @transaction.atomic
    def mark_invoice_paid(invoice: PlatformBillingInvoice, paid_by=None):
        if invoice.status == PlatformBillingInvoice.Status.PAID:
            return  # Already paid
        invoice.status = PlatformBillingInvoice.Status.PAID
        invoice.paid_by = paid_by
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=["status", "paid_by", "paid_at"])

        # Credit wallet
        if invoice.invoice_type == PlatformBillingInvoice.InvoiceType.SMS_RECHARGE:
            SMSCreditService.credit_wallet(
                company=invoice.company, amount_rial=invoice.amount_rial,
                invoice=invoice, created_by=paid_by,
            )
