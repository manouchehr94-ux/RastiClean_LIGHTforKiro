"""Order event dispatchers.

Database writes happen inside services; external side effects are scheduled via
``transaction.on_commit`` so notifications/SMS are sent only after the order is
successfully committed.
"""
from __future__ import annotations

from django.db import transaction


def dispatch_order_available_events(*, order) -> None:
    """Notify eligible technicians about a newly available unassigned order."""
    transaction.on_commit(lambda: _run_order_available_events(order_id=order.id))


def _run_order_available_events(*, order_id: int) -> None:
    from apps.orders.models import Order
    from apps.orders.technician_notifications import notify_visible_technicians_for_order

    order = Order.objects.select_related(
        "company", "customer", "service_category", "technician",
    ).filter(id=order_id).first()
    if order is None:
        return

    try:
        notify_visible_technicians_for_order(order=order)
    except Exception:
        # Notification failures must never break the operational order flow.
        pass
