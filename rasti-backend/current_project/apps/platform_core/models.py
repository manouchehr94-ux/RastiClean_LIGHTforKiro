"""
Platform-level models.

These models are NOT tenant-scoped.
They belong to the platform owner and manage global resources.
"""
from django.conf import settings
from django.db import models


class Plan(models.Model):
    """
    Subscription plan available on the platform.
    Platform-level model — not tenant-scoped.
    """

    name = models.CharField(max_length=100)
    code = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    price_yearly = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    max_users = models.PositiveIntegerField(default=5)
    max_technicians = models.PositiveIntegerField(default=10)
    max_orders_per_month = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price_monthly"]

    def __str__(self) -> str:
        return self.name


class Subscription(models.Model):
    """
    A company's subscription to a plan.
    Links a tenant (Company) to a Plan with billing dates.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TRIAL = "trial", "Trial"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    company = models.OneToOneField(
        "tenants.Company",
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TRIAL,
    )
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.company.name} - {self.plan.name} ({self.status})"



class PlatformMessage(models.Model):
    """
    Internal message center for Platform Owner.

    Stores messages that the Platform Owner sends to companies/users
    or receives from the system. Currently internal-only — no real
    SMS/email delivery.

    TODO (Future):
    - Connect to SMS provider for actual delivery
    - Connect to email provider for email delivery
    - Add tenant company inbox for inbound messages
    - Add message templates system
    - Add WhatsApp/Telegram channel support
    """

    class RecipientType(models.TextChoices):
        PLATFORM_OWNER = "PLATFORM_OWNER", "مدیر پلتفرم"
        COMPANY = "COMPANY", "شرکت"
        COMPANY_ADMIN = "COMPANY_ADMIN", "مدیر شرکت"
        TECHNICIAN = "TECHNICIAN", "تکنسین"
        CUSTOMER = "CUSTOMER", "مشتری"
        CUSTOM = "CUSTOM", "سفارشی"

    class Channel(models.TextChoices):
        INTERNAL = "INTERNAL", "داخلی"
        SMS_FUTURE = "SMS_FUTURE", "پیامک (آینده)"
        EMAIL_FUTURE = "EMAIL_FUTURE", "ایمیل (آینده)"

    class Direction(models.TextChoices):
        INBOUND = "INBOUND", "دریافتی"
        OUTBOUND = "OUTBOUND", "ارسالی"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "پیش‌نویس"
        QUEUED = "QUEUED", "در صف ارسال"
        SENT = "SENT", "ارسال شده"
        FAILED = "FAILED", "ناموفق"
        READ = "READ", "خوانده شده"

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="sent_platform_messages",
        help_text="Null if system-generated.",
    )
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="received_platform_messages",
    )
    recipient_company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="platform_messages",
    )
    recipient_type = models.CharField(
        max_length=20,
        choices=RecipientType.choices,
        default=RecipientType.COMPANY,
    )
    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.INTERNAL,
    )
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        default=Direction.OUTBOUND,
    )
    subject = models.CharField(max_length=300)
    body = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Platform Message"
        verbose_name_plural = "Platform Messages"

    def __str__(self) -> str:
        return f"{self.subject} ({self.get_status_display()})"



class GlobalSMSPricingSetting(models.Model):
    """Platform-wide SMS pricing. Only one row should exist (singleton)."""
    characters_per_sms = models.PositiveIntegerField(default=60)
    price_per_sms_rial = models.PositiveIntegerField(default=520)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "SMS Pricing Setting"

    def __str__(self):
        return f"{self.price_per_sms_rial} rial/sms, {self.characters_per_sms} chars/sms"


class CompanySMSWallet(models.Model):
    """SMS credit wallet for a tenant company."""
    company = models.OneToOneField("tenants.Company", on_delete=models.CASCADE, related_name="sms_wallet")
    balance_rial = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company SMS Wallet"

    def __str__(self):
        return f"{self.company.name}: {self.balance_rial} rial"


class CompanySMSTransaction(models.Model):
    """Transaction record for SMS wallet changes."""
    class TransactionType(models.TextChoices):
        CREDIT = "CREDIT", "شارژ"
        DEBIT = "DEBIT", "مصرف"
        ADJUSTMENT = "ADJUSTMENT", "تعدیل"
        BLOCKED = "BLOCKED", "مسدود (اعتبار ناکافی)"

    company = models.ForeignKey("tenants.Company", on_delete=models.CASCADE, related_name="sms_transactions")
    wallet = models.ForeignKey(CompanySMSWallet, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=15, choices=TransactionType.choices)
    amount_rial = models.BigIntegerField()
    sms_parts = models.PositiveIntegerField(default=0)
    message_length = models.PositiveIntegerField(default=0)
    balance_after = models.BigIntegerField()
    description = models.CharField(max_length=300, blank=True)
    related_invoice = models.ForeignKey("platform_core.PlatformBillingInvoice", on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company.name} {self.transaction_type} {self.amount_rial}"


class PlatformBillingInvoice(models.Model):
    """Invoice from Platform Owner to tenant company."""
    class InvoiceType(models.TextChoices):
        SMS_RECHARGE = "SMS_RECHARGE", "شارژ پیامک"
        SUBSCRIPTION = "SUBSCRIPTION", "اشتراک"
        MANUAL = "MANUAL", "دستی"
        OTHER = "OTHER", "سایر"

    class Status(models.TextChoices):
        UNPAID = "UNPAID", "پرداخت نشده"
        PAID = "PAID", "پرداخت شده"
        CANCELED = "CANCELED", "لغو شده"

    company = models.ForeignKey("tenants.Company", on_delete=models.CASCADE, related_name="platform_invoices")
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_type = models.CharField(max_length=20, choices=InvoiceType.choices, default=InvoiceType.SMS_RECHARGE)
    amount_rial = models.BigIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNPAID)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_platform_invoices")
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="paid_platform_invoices")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.company.name} ({self.get_status_display()})"
