"""
Phase 25: Cancel request event dispatchers.

Side effects (notifications) are scheduled via ``transaction.on_commit``
so they only fire after the order status change is successfully committed.
"""
from __future__ import annotations

from django.db import transaction


def dispatch_cancel_request_events(*, order, reason: str = "") -> None:
    """Notify admins/operators that a technician requested cancellation."""
    transaction.on_commit(
        lambda: _run_cancel_request_events(order_id=order.id, reason=reason)
    )


def dispatch_cancel_approved_events(*, order) -> None:
    """Notify the assigned technician that cancellation was approved."""
    transaction.on_commit(
        lambda: _run_cancel_approved_events(order_id=order.id)
    )


def dispatch_cancel_rejected_events(*, order) -> None:
    """Notify the assigned technician that cancellation was rejected."""
    transaction.on_commit(
        lambda: _run_cancel_rejected_events(order_id=order.id)
    )


# =============================================================================
# Internal runners (executed after commit)
# =============================================================================


def _run_cancel_request_events(*, order_id: int, reason: str) -> None:
    from apps.accounts.models import CompanyUser, UserRole
    from apps.notifications.models import Notification, NotificationSetting
    from apps.notifications.services import NotificationCreateService
    from apps.orders.models import Order

    order = (
        Order.objects.select_related("company", "technician", "technician__user")
        .filter(id=order_id)
        .first()
    )
    if order is None:
        return

    tech_name = ""
    if order.technician and order.technician.user:
        tech_name = order.technician.user.get_full_name()

    title = "درخواست لغو سفارش"
    message = (
        f"تکنسین {tech_name} درخواست لغو سفارش #{order.id} "
        f"({order.display_customer_name or '-'}) را ثبت کرد."
    )
    if reason:
        message += f"\nدلیل: {reason}"

    # Notify all active COMPANY_ADMIN and COMPANY_STAFF in the same company
    admins = CompanyUser.objects.filter(
        company=order.company,
        role__in=[UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF],
        is_active=True,
    )
    for admin in admins:
        try:
            NotificationCreateService.create(
                company=order.company,
                recipient=admin,
                notification_type=Notification.NotificationType.ORDER_CANCEL_REQUESTED,
                title=title,
                message=message,
                related_order=order,
                event_key=NotificationSetting.EventKey.ORDER_CANCEL_REQUESTED_ADMIN,
            )
        except Exception:
            pass

    try:
        from apps.sms.services import SMSEventHooks
        SMSEventHooks.on_order_cancel_requested_admin(order=order, reason=reason)
    except Exception:
        pass


def _run_cancel_approved_events(*, order_id: int) -> None:
    from apps.notifications.models import Notification, NotificationSetting
    from apps.notifications.services import NotificationCreateService
    from apps.orders.models import Order

    order = (
        Order.objects.select_related("company", "technician", "technician__user")
        .filter(id=order_id)
        .first()
    )
    if order is None:
        return

    # Notify the technician who was assigned
    tech_user = None
    if order.technician and order.technician.user:
        tech_user = order.technician.user
    if tech_user is None:
        return

    try:
        NotificationCreateService.create(
            company=order.company,
            recipient=tech_user,
            notification_type=Notification.NotificationType.ORDER_CANCEL_APPROVED,
            title="درخواست لغو تایید شد",
            message=f"درخواست لغو سفارش #{order.id} توسط مدیر تایید شد.",
            related_order=order,
            event_key=NotificationSetting.EventKey.ORDER_CANCEL_APPROVED_TECHNICIAN,
        )
    except Exception:
        pass

    try:
        from apps.sms.services import SMSEventHooks
        SMSEventHooks.on_order_cancel_approved_technician(order=order)
    except Exception:
        pass


def _run_cancel_rejected_events(*, order_id: int) -> None:
    from apps.notifications.models import Notification, NotificationSetting
    from apps.notifications.services import NotificationCreateService
    from apps.orders.models import Order

    order = (
        Order.objects.select_related("company", "technician", "technician__user")
        .filter(id=order_id)
        .first()
    )
    if order is None:
        return

    tech_user = None
    if order.technician and order.technician.user:
        tech_user = order.technician.user
    if tech_user is None:
        return

    try:
        NotificationCreateService.create(
            company=order.company,
            recipient=tech_user,
            notification_type=Notification.NotificationType.ORDER_CANCEL_REJECTED,
            title="درخواست لغو رد شد",
            message=(
                f"درخواست لغو سفارش #{order.id} توسط مدیر رد شد. "
                f"سفارش به وضعیت قبلی بازگشت."
            ),
            related_order=order,
            event_key=NotificationSetting.EventKey.ORDER_CANCEL_REJECTED_TECHNICIAN,
        )
    except Exception:
        pass

    try:
        from apps.sms.services import SMSEventHooks
        SMSEventHooks.on_order_cancel_rejected_technician(order=order)
    except Exception:
        pass
