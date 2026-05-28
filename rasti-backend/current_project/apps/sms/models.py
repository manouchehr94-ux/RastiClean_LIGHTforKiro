"""
SMS - Models.

Tenant-scoped SMS outbox and provider configuration.
Each company can configure their own SMS provider.
"""
from django.db import models

from apps.common.models import CompanyOwnedModel


class SMSProvider(CompanyOwnedModel):
    """SMS provider configuration for a company."""

    class ProviderType(models.TextChoices):
        KAVENEGAR = "kavenegar", "Kavenegar"
        GHASEDAK = "ghasedak", "Ghasedak"
        MELIPAYAMAK = "melipayamak", "MeliPayamak"
        FAKE = "fake", "Fake (Testing)"

    name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=20, choices=ProviderType.choices)
    api_key = models.CharField(max_length=300)
    sender_number = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.provider_type})"


class SMSTemplate(CompanyOwnedModel):
    """
    Company-scoped SMS template.
    Each company can customise message text for each event key.
    """

    class TemplateKey(models.TextChoices):
        ORDER_CREATED_ADMIN = "order_created_admin", "سفارش جدید - مدیر"
        ORDER_AVAILABLE_TECHNICIAN = "order_available_technician", "سفارش جدید - تکنسین"
        ORDER_ASSIGNED_TECHNICIAN = "order_assigned_technician", "تخصیص سفارش - تکنسین"
        ORDER_ACCEPTED_CUSTOMER = "order_accepted_customer", "قبول سفارش - مشتری"
        ORDER_COMPLETED_CUSTOMER = "order_completed_customer", "اتمام سفارش - مشتری"
        ORDER_CANCEL_REQUESTED_ADMIN = "order_cancel_requested_admin", "درخواست لغو - مدیر"
        ORDER_CANCEL_APPROVED_TECHNICIAN = "order_cancel_approved_technician", "تایید لغو - تکنسین"
        ORDER_CANCEL_REJECTED_TECHNICIAN = "order_cancel_rejected_technician", "رد لغو - تکنسین"
        INVOICE_ISSUED_CUSTOMER = "invoice_issued_customer", "صدور فاکتور - مشتری"
        PAYMENT_SUCCESS_CUSTOMER = "payment_success_customer", "پرداخت موفق - مشتری"
        PAYMENT_FAILED_CUSTOMER = "payment_failed_customer", "پرداخت ناموفق - مشتری"
        SURVEY_REQUEST_CUSTOMER = "survey_request_customer", "نظرسنجی - مشتری"

    key = models.CharField(max_length=50, choices=TemplateKey.choices)
    title = models.CharField(max_length=200)
    template_text = models.TextField(
        help_text="Django template syntax. Variables: {{ order_id }}, {{ customer_name }}, etc.",
    )
    is_active = models.BooleanField(default=True)
    send_start_time = models.TimeField(
        null=True, blank=True,
        help_text="Earliest time of day to send (e.g. 08:00).",
    )
    send_end_time = models.TimeField(
        null=True, blank=True,
        help_text="Latest time of day to send (e.g. 22:00).",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "key"],
                name="unique_sms_template_per_company",
            ),
        ]
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.title} ({self.get_key_display()})"


class SMSOutbox(CompanyOwnedModel):
    """
    SMS outbox record.
    Every SMS attempt is logged here for audit and retry.

    Statuses:
        PENDING -> SENT
        PENDING -> FAILED
        PENDING -> CANCELLED
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    provider = models.ForeignKey(
        SMSProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    template = models.ForeignKey(
        SMSTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbox_messages",
    )
    template_key = models.CharField(
        max_length=50,
        choices=SMSTemplate.TemplateKey.choices,
        blank=True,
    )
    phone_number = models.CharField(max_length=15)
    message = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    provider_message_id = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    send_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Scheduled send time (for time-window logic).",
    )
    order_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    invoice_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "SMS Outbox"
        verbose_name_plural = "SMS Outbox"

    def __str__(self) -> str:
        return f"SMS to {self.phone_number} ({self.status})"
