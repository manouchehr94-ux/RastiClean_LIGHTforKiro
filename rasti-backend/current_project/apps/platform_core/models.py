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



class CommunicationTemplate(models.Model):
    """
    Platform-owned communication template.

    ONLY Platform Owner can create/edit these.
    Tenant companies can ONLY toggle is_enabled for their own company
    (via CommunicationTemplateCompanySetting) when allow_company_toggle=True.

    Resolution order:
    1. If is_active=False → globally disabled, never used
    2. If is_required=True → always used, tenant cannot disable
    3. If allow_company_toggle=True → check CommunicationTemplateCompanySetting
    4. If company setting is_enabled=False → skip for that company
    5. Otherwise → use this template
    """

    class Channel(models.TextChoices):
        SMS = "SMS", "پیامک"
        EMAIL = "EMAIL", "ایمیل"
        IN_APP = "IN_APP", "اعلان داخلی"
        INTERNAL = "INTERNAL", "پیام داخلی"

    class RecipientType(models.TextChoices):
        COMPANY_ADMIN = "COMPANY_ADMIN", "مدیر شرکت"
        TECHNICIAN = "TECHNICIAN", "تکنسین"
        CUSTOMER = "CUSTOMER", "مشتری"
        PLATFORM_OWNER = "PLATFORM_OWNER", "مدیر پلتفرم"

    event_key = models.CharField(
        max_length=80,
        db_index=True,
        help_text="Machine-readable event key (e.g. order_created_admin).",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    recipient_type = models.CharField(max_length=20, choices=RecipientType.choices)
    title = models.CharField(max_length=300, help_text="Notification/message title.")
    body = models.TextField(help_text="Template body. Supports {{ placeholders }}.")
    action_label = models.CharField(
        max_length=100, blank=True,
        help_text="Button/link label (e.g. 'مشاهده سفارش').",
    )
    action_url_template = models.CharField(
        max_length=300, blank=True,
        help_text="URL template with placeholders (e.g. /{{ company_code }}/admin/orders/{{ order_id }}/).",
    )
    allowed_placeholders = models.TextField(
        blank=True,
        help_text="Comma-separated list of allowed placeholders.",
    )

    # Platform Owner control flags
    is_active = models.BooleanField(
        default=True,
        help_text="Globally active. If False, never used anywhere.",
    )
    is_required = models.BooleanField(
        default=False,
        help_text="If True, tenant companies cannot disable this template.",
    )
    allow_company_toggle = models.BooleanField(
        default=True,
        help_text="If True, tenant admins can enable/disable for their company.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event_key", "channel"]
        constraints = [
            models.UniqueConstraint(
                fields=["event_key", "channel", "recipient_type"],
                name="unique_comm_template_event_channel_recipient",
            ),
        ]
        verbose_name = "Communication Template"
        verbose_name_plural = "Communication Templates"

    def __str__(self) -> str:
        return f"{self.event_key} / {self.get_channel_display()} → {self.get_recipient_type_display()}"


class CommunicationTemplateCompanySetting(models.Model):
    """
    Per-company toggle for a communication template.

    Tenant admin can ONLY set is_enabled True/False.
    They cannot edit the template content.
    This row only exists if allow_company_toggle=True on the template.
    """

    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.CASCADE,
        related_name="communication_settings",
    )
    template = models.ForeignKey(
        CommunicationTemplate,
        on_delete=models.CASCADE,
        related_name="company_settings",
    )
    is_enabled = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "template"],
                name="unique_comm_setting_per_company_template",
            ),
        ]
        verbose_name = "Company Communication Setting"
        verbose_name_plural = "Company Communication Settings"

    def __str__(self) -> str:
        status = "فعال" if self.is_enabled else "غیرفعال"
        return f"{self.company} / {self.template.event_key} → {status}"
