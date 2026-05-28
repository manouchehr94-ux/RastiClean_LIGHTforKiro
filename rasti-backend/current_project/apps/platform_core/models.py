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



class PaymentGatewayProvider(models.TextChoices):
    """Available payment gateway providers."""
    MOCK = "MOCK", "آزمایشی (بدون اتصال)"
    MANUAL = "MANUAL", "پرداخت دستی"
    ZARINPAL_FUTURE = "ZARINPAL_FUTURE", "زرین‌پال (آینده)"
    ZIBAL_FUTURE = "ZIBAL_FUTURE", "زیبال (آینده)"
    IDPAY_FUTURE = "IDPAY_FUTURE", "آیدی‌پی (آینده)"
    PAYPING_FUTURE = "PAYPING_FUTURE", "پی‌پینگ (آینده)"


class PlatformPaymentGatewaySetting(models.Model):
    """
    Payment gateway for Platform Owner (SMS recharge, subscriptions).
    Singleton — only one active setting.
    """
    provider = models.CharField(max_length=20, choices=PaymentGatewayProvider.choices, default=PaymentGatewayProvider.MOCK)
    is_active = models.BooleanField(default=False)
    merchant_id = models.CharField(max_length=200, blank=True, help_text="Merchant ID or API key (masked in UI)")
    terminal_id = models.CharField(max_length=100, blank=True)
    callback_base_url = models.CharField(max_length=300, blank=True, help_text="e.g. https://rastiservice.ir")
    sandbox_mode = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform Payment Gateway"

    def __str__(self):
        return f"Platform: {self.get_provider_display()} ({'active' if self.is_active else 'inactive'})"

    @property
    def merchant_id_masked(self):
        if not self.merchant_id or len(self.merchant_id) < 5:
            return "****"
        return "****" + self.merchant_id[-4:]


class CompanyPaymentGatewaySetting(models.Model):
    """
    Payment gateway for a tenant company (order/invoice payments).
    Each company has its own gateway configuration.
    """
    company = models.OneToOneField("tenants.Company", on_delete=models.CASCADE, related_name="payment_gateway")
    provider = models.CharField(max_length=20, choices=PaymentGatewayProvider.choices, default=PaymentGatewayProvider.MOCK)
    is_active = models.BooleanField(default=False)
    merchant_id = models.CharField(max_length=200, blank=True, help_text="Merchant ID or API key (masked in UI)")
    terminal_id = models.CharField(max_length=100, blank=True)
    callback_base_url = models.CharField(max_length=300, blank=True)
    sandbox_mode = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company Payment Gateway"

    def __str__(self):
        return f"{self.company.name}: {self.get_provider_display()}"

    @property
    def merchant_id_masked(self):
        if not self.merchant_id or len(self.merchant_id) < 5:
            return "****"
        return "****" + self.merchant_id[-4:]
