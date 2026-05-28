"""
Notifications - Models.

Tenant-scoped in-app notification system.
All notifications MUST be filtered by company.
"""
from django.db import models

from apps.common.models import CompanyOwnedModel


class Notification(CompanyOwnedModel):
    """
    In-app notification for company users.

    Types:
    - ORDER_CREATED: Admin/staff notified of new order
    - ORDER_ACCEPTED: Customer notified technician accepted
    - ORDER_COMPLETED: Customer notified order is done
    - INVOICE_ISSUED: Customer notified invoice ready
    - PAYMENT_PAID: Customer + admin notified payment succeeded
    - PAYMENT_FAILED: Customer notified payment failed
    """

    class NotificationType(models.TextChoices):
        ORDER_CREATED = "order_created", "Order Created"
        ORDER_AVAILABLE = "order_available", "Order Available"
        ORDER_ASSIGNED = "order_assigned", "Order Assigned"
        ORDER_ACCEPTED = "order_accepted", "Order Accepted"
        ORDER_COMPLETED = "order_completed", "Order Completed"
        ORDER_CANCEL_REQUESTED = "order_cancel_requested", "Order Cancel Requested"
        ORDER_CANCEL_APPROVED = "order_cancel_approved", "Order Cancel Approved"
        ORDER_CANCEL_REJECTED = "order_cancel_rejected", "Order Cancel Rejected"
        INVOICE_ISSUED = "invoice_issued", "Invoice Issued"
        PAYMENT_PAID = "payment_paid", "Payment Paid"
        PAYMENT_FAILED = "payment_failed", "Payment Failed"

    recipient = models.ForeignKey(
        "accounts.CompanyUser",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # Optional references to related objects
    related_order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    related_invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "recipient", "is_read"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} → {self.recipient}"



class NotificationSetting(CompanyOwnedModel):
    """
    Per-company switches for in-app notifications and SMS notifications.

    Each row controls one business event, for example:
    - new order
    - technician assignment
    - cancel request
    - cancel approved/rejected
    - invoice/payment events

    The setting is intentionally separate from SMS templates:
    - NotificationSetting controls whether an event is allowed to send.
    - SMSTemplate controls the SMS wording and SMS active/inactive state.
    """

    class EventKey(models.TextChoices):
        ORDER_CREATED_ADMIN = "order_created_admin", "سفارش جدید / درخواست سفارش"
        ORDER_AVAILABLE_TECHNICIAN = "order_available_technician", "سفارش جدید برای تکنسین"
        ORDER_ASSIGNED_TECHNICIAN = "order_assigned_technician", "تخصیص سفارش به تکنسین"
        ORDER_ACCEPTED_CUSTOMER = "order_accepted_customer", "تایید / پذیرش سفارش"
        ORDER_COMPLETED_CUSTOMER = "order_completed_customer", "اتمام سفارش"
        ORDER_CANCEL_REQUESTED_ADMIN = "order_cancel_requested_admin", "درخواست لغو سفارش"
        ORDER_CANCEL_APPROVED_TECHNICIAN = "order_cancel_approved_technician", "تایید لغو سفارش"
        ORDER_CANCEL_REJECTED_TECHNICIAN = "order_cancel_rejected_technician", "رد لغو سفارش"
        INVOICE_ISSUED_CUSTOMER = "invoice_issued_customer", "صدور فاکتور"
        PAYMENT_SUCCESS_CUSTOMER = "payment_success_customer", "پرداخت موفق"
        PAYMENT_FAILED_CUSTOMER = "payment_failed_customer", "پرداخت ناموفق"
        SURVEY_REQUEST_CUSTOMER = "survey_request_customer", "نظرسنجی"

    event_key = models.CharField(max_length=60, choices=EventKey.choices)
    title = models.CharField(max_length=200, blank=True)
    in_app_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["event_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "event_key"],
                name="unique_notification_setting_per_company_event",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.company} - {self.event_key}"
