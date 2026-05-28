"""
SMS - Selectors.

Read operations for SMS outbox. Always company-scoped.
"""
from typing import Optional

from django.db.models import QuerySet

from .models import SMSOutbox, SMSProvider


class SMSOutboxSelector:
    """Read operations for SMSOutbox."""

    @staticmethod
    def get_for_company(*, company) -> QuerySet[SMSOutbox]:
        """Get all SMS records for a company (admin view)."""
        return SMSOutbox.objects.filter(company=company)

    @staticmethod
    def get_pending(*, company) -> QuerySet[SMSOutbox]:
        """Get pending SMS messages for a company."""
        return SMSOutbox.objects.filter(company=company, status=SMSOutbox.Status.PENDING)


class SMSProviderSelector:
    """Read operations for SMSProvider."""

    @staticmethod
    def get_active_for_company(*, company) -> Optional[SMSProvider]:
        """Get the active SMS provider for a company."""
        return SMSProvider.objects.filter(company=company, is_active=True).first()
