"""Post-assignment event hooks for order workflow.

Keep side effects out of views/services. Assignment services call
`dispatch_order_assigned_events()` after the database transaction commits.
"""
from __future__ import annotations

from django.db import transaction


def dispatch_order_assigned_events(*, order, technician) -> None:
    """Run notification/SMS hooks after an admin assignment is committed."""
    transaction.on_commit(lambda: _run_order_assigned_events(order_id=order.id, technician_id=technician.id))


def _run_order_assigned_events(*, order_id: int, technician_id: int) -> None:
    from apps.accounts.models import Technician
    from apps.notifications.models import Notification, NotificationSetting
    from apps.notifications.services import NotificationCreateService, NotificationEventHooks
    from apps.orders.models import Order

    order = Order.objects.select_related("company", "customer", "technician").filter(id=order_id).first()
    technician = Technician.objects.select_related("user", "company").filter(id=technician_id).first()
    if order is None or technician is None:
        return

    # In-app notification for the assigned technician.
    if technician.user_id:
        NotificationCreateService.create(
            company=order.company,
            recipient=technician.user,
            notification_type=Notification.NotificationType.ORDER_ASSIGNED,
            title="سفارش جدید به شما تخصیص داده شد",
            message=f"سفارش #{order.id} برای {order.display_customer_name or 'مشتری'} به شما تخصیص داده شد.",
            related_order=order,
            event_key=NotificationSetting.EventKey.ORDER_ASSIGNED_TECHNICIAN,
        )

    # Existing customer-facing hooks. They are intentionally wrapped so a
    # notification/SMS failure never rolls back the operational assignment.
    try:
        NotificationEventHooks.on_order_accepted(order=order)
    except Exception:
        pass

    try:
        from apps.sms.services import SMSEventHooks
        # Customer SMS through the existing hook.
        SMSEventHooks.on_order_accepted(order=order)
        # Technician SMS through template-based hook.
        SMSEventHooks.on_order_assigned_technician(order=order)
    except Exception:
        pass
