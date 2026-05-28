"""
SMS - Service Layer.

Handles SMS queuing and sending.
Architecture is ready for background jobs (Celery) but currently synchronous.

IMPORTANT: Each company uses its own SMS provider configuration.
"""
import re
from typing import Optional, Tuple

from django.template import Context, Template
from django.utils import timezone

from .models import SMSOutbox, SMSProvider, SMSTemplate
from .providers import get_sms_provider
from .providers.base import SMSSendRequest
from .selectors import SMSProviderSelector


# =============================================================================
# PHONE NUMBER NORMALIZATION / VALIDATION (Phase 26E)
# =============================================================================

# Iranian mobile number regex: after normalization must be 09xxxxxxxxx (11 digits)
_IRAN_MOBILE_REGEX = re.compile(r"^09[0-9]{9}$")


def normalize_sms_phone_number(raw: str) -> Optional[str]:
    """
    Normalize an Iranian mobile phone number to 09xxxxxxxxx format.

    Accepted input formats:
        09123456789
        9123456789
        +989123456789
        989123456789
        00989123456789

    Returns:
        Normalized phone string (09xxxxxxxxx) or None if invalid.
    """
    if not raw:
        return None

    # Strip whitespace, dashes, parentheses
    phone = re.sub(r"[\s\-\(\)]+", "", raw.strip())

    # Remove leading +
    if phone.startswith("+"):
        phone = phone[1:]

    # Remove leading 0098
    if phone.startswith("0098"):
        phone = "0" + phone[4:]
    # Remove leading 98 (but not 09...)
    elif phone.startswith("98") and len(phone) == 12:
        phone = "0" + phone[2:]
    # Add leading 0 if starts with 9 and is 10 digits
    elif phone.startswith("9") and len(phone) == 10:
        phone = "0" + phone

    # Validate final format
    if _IRAN_MOBILE_REGEX.match(phone):
        return phone
    return None


def validate_sms_phone_number(raw: str) -> Tuple[bool, str, str]:
    """
    Validate and normalize an Iranian mobile phone number.

    Returns:
        Tuple of (is_valid, normalized_number, error_message).
        If invalid, normalized_number is empty and error_message explains why.
    """
    if not raw or not raw.strip():
        return False, "", "شماره گیرنده الزامی است."

    normalized = normalize_sms_phone_number(raw)
    if normalized is None:
        return False, "", "شماره تلفن وارد شده معتبر نیست. فرمت صحیح: 09xxxxxxxxx"

    return True, normalized, ""


class SMSQueueService:
    """
    Queue an SMS for sending.
    Creates an SMSOutbox record with PENDING status.
    """

    @staticmethod
    def queue(
        *,
        company,
        phone_number: str,
        message: str,
        template: Optional[SMSTemplate] = None,
        template_key: str = "",
        send_at=None,
        order_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
    ) -> Optional[SMSOutbox]:
        """
        Queue an SMS message for sending.

        Phone number is normalized before queuing. If the phone number is
        invalid/empty, returns None without creating an outbox row.

        SMS Credit enforcement:
        - Checks company SMS wallet balance before queuing.
        - If insufficient credit: creates FAILED outbox record + BLOCKED transaction.
        - If sufficient: debits wallet atomically, then queues SMS.

        Args:
            company: The tenant company.
            phone_number: Recipient phone number (will be normalized).
            message: SMS message content.
            template: Optional SMSTemplate instance.
            template_key: Optional template key string.
            send_at: Optional scheduled send time.
            order_id: Optional related order ID.
            invoice_id: Optional related invoice ID.

        Returns:
            Created SMSOutbox record (PENDING or FAILED), or None if phone invalid.
        """
        # Phase 26E: Normalize and validate phone number
        normalized = normalize_sms_phone_number(phone_number)
        if normalized is None:
            return None

        # === SMS CREDIT ENFORCEMENT ===
        # Check wallet balance before queuing. Block if insufficient.
        from apps.platform_core.services_sms_credit import SMSCreditService

        if not SMSCreditService.has_sufficient_credit(company=company, message_text=message):
            # Record BLOCKED wallet transaction
            SMSCreditService.debit_for_sms(
                company=company,
                message_text=message,
                description=f"مسدود: اعتبار پیامک ناکافی ({normalized})",
            )
            # Create FAILED outbox record so it appears in logs/diagnostics
            provider = SMSProviderSelector.get_active_for_company(company=company)
            outbox = SMSOutbox.objects.create(
                company=company,
                provider=provider,
                template=template,
                template_key=template_key,
                phone_number=normalized,
                message=message,
                status=SMSOutbox.Status.FAILED,
                error_message="اعتبار پیامک ناکافی است. لطفاً اعتبار شرکت را شارژ کنید.",
                send_at=send_at,
                order_id=order_id,
                invoice_id=invoice_id,
            )
            return outbox

        # Sufficient credit — debit wallet atomically
        SMSCreditService.debit_for_sms(
            company=company,
            message_text=message,
            description=f"ارسال پیامک به {normalized}",
        )

        # Queue the SMS normally
        provider = SMSProviderSelector.get_active_for_company(company=company)

        outbox = SMSOutbox.objects.create(
            company=company,
            provider=provider,
            template=template,
            template_key=template_key,
            phone_number=normalized,
            message=message,
            status=SMSOutbox.Status.PENDING,
            send_at=send_at,
            order_id=order_id,
            invoice_id=invoice_id,
        )
        return outbox


# =============================================================================
# SMS SENDING SAFETY SERVICE (Phase 26F)
# =============================================================================


class SMSSendingSafetyService:
    """
    Determine whether SMS sending is enabled/safe for a company.

    Safety convention (no migration needed):
    - Sending is ENABLED if the company has at least one active SMSProvider.
    - Sending is DISABLED if no active provider exists.
    - This matches the existing project behavior where SMSProviderSelector
      returns None when no active provider is configured.

    This service provides an explicit, reusable check that the processor,
    diagnostics, manual retry, and bulk retry all use before attempting to
    send via a provider.
    """

    DISABLED_ERROR = "ارسال پیامک برای این شرکت غیرفعال است (ارائه‌دهنده فعال یافت نشد)."

    @staticmethod
    def is_sending_enabled(*, company) -> bool:
        """
        Check whether SMS sending is enabled for a company.

        Returns True if an active SMS provider is configured.
        """
        provider = SMSProviderSelector.get_active_for_company(company=company)
        return provider is not None

    @staticmethod
    def get_status(*, company) -> dict:
        """
        Get a summary of sending safety status for a company.

        Returns:
            Dict with keys: enabled (bool), reason (str).
        """
        provider = SMSProviderSelector.get_active_for_company(company=company)
        if provider is None:
            return {
                "enabled": False,
                "reason": SMSSendingSafetyService.DISABLED_ERROR,
            }
        return {
            "enabled": True,
            "reason": "",
        }


class SMSSendService:
    """
    Send a single SMS via the company's provider.
    Currently synchronous -- ready for Celery task wrapper.

    Phase 26F: Checks sending safety before calling provider.
    """

    @staticmethod
    def send(*, sms: SMSOutbox) -> SMSOutbox:
        """
        Attempt to send a queued SMS.

        Phase 26F safety: If sending is disabled for the company (no active
        provider), the message is marked FAILED with a clear error without
        calling any provider.

        Args:
            sms: SMSOutbox record to send.

        Returns:
            Updated SMSOutbox record (SENT or FAILED).
        """
        if sms.status != SMSOutbox.Status.PENDING:
            return sms

        # Phase 26F: Explicit safety check
        if not SMSSendingSafetyService.is_sending_enabled(company=sms.company):
            sms.status = SMSOutbox.Status.FAILED
            sms.error_message = SMSSendingSafetyService.DISABLED_ERROR
            sms.save(update_fields=["status", "error_message", "updated_at"])
            return sms

        if not sms.provider:
            sms.status = SMSOutbox.Status.FAILED
            sms.error_message = "No SMS provider configured."
            sms.save(update_fields=["status", "error_message", "updated_at"])
            return sms

        provider_impl = get_sms_provider(sms.provider)
        if provider_impl is None:
            sms.status = SMSOutbox.Status.FAILED
            sms.error_message = f"No implementation for provider: {sms.provider.provider_type}"
            sms.save(update_fields=["status", "error_message", "updated_at"])
            return sms

        # Send via provider
        request = SMSSendRequest(
            phone_number=sms.phone_number,
            message=sms.message,
        )
        response = provider_impl.send(request)

        if response.success:
            sms.status = SMSOutbox.Status.SENT
            sms.provider_message_id = response.message_id
            sms.sent_at = timezone.now()
            sms.save(update_fields=[
                "status", "provider_message_id", "sent_at", "updated_at"
            ])
        else:
            sms.status = SMSOutbox.Status.FAILED
            sms.error_message = response.error_message
            sms.save(update_fields=["status", "error_message", "updated_at"])

        return sms


class SMSBulkSendService:
    """Send all pending SMS for a company."""

    @staticmethod
    def send_all_pending(*, company) -> list[SMSOutbox]:
        """
        Send all pending SMS messages for a company.
        Returns list of processed SMSOutbox records.
        """
        pending = SMSOutbox.objects.filter(
            company=company, status=SMSOutbox.Status.PENDING
        )
        results = []
        for sms in pending:
            result = SMSSendService.send(sms=sms)
            results.append(result)
        return results


# =============================================================================
# SMS TEMPLATE RENDERING SERVICE
# =============================================================================


class SMSTemplateRenderService:
    """Render SMS template text with context variables."""

    @staticmethod
    def render(*, template_text: str, context: dict) -> str:
        """Render Django template string with the given context."""
        tpl = Template(template_text)
        return tpl.render(Context(context))

    @staticmethod
    def build_order_context(*, order) -> dict:
        """Build template context from an order instance."""
        customer_name = ""
        customer_phone = ""
        if order.customer:
            customer_name = f"{order.customer.first_name} {order.customer.last_name}".strip()
            customer_phone = order.customer.phone or ""
        if order.customer_name:
            customer_name = order.customer_name
        if order.customer_phone:
            customer_phone = order.customer_phone

        technician_name = ""
        if order.technician and order.technician.user:
            technician_name = order.technician.user.get_full_name()

        return {
            "order_id": order.id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "technician_name": technician_name,
            "order_title": order.title,
            "order_status": order.get_status_display(),
            "company_name": order.company.name if order.company else "",
        }

    @staticmethod
    def build_invoice_context(*, invoice) -> dict:
        """Build template context from an invoice instance."""
        customer_name = ""
        customer_phone = ""
        if invoice.customer:
            customer_name = f"{invoice.customer.first_name} {invoice.customer.last_name}".strip()
            customer_phone = invoice.customer.phone or ""

        return {
            "invoice_id": invoice.id,
            "invoice_number": getattr(invoice, "invoice_number", ""),
            "total_amount": str(getattr(invoice, "total_amount", 0)),
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "company_name": invoice.company.name if invoice.company else "",
        }


# =============================================================================
# SMS TIME WINDOW SERVICE
# =============================================================================


class SMSTimeWindowService:
    """Calculate scheduled send time based on template time windows."""

    @staticmethod
    def calculate_send_at(*, template: SMSTemplate, company) -> Optional[object]:
        """
        Determine if the SMS should be delayed to fit the time window.

        Returns:
            None if no delay needed (send immediately).
            datetime if the SMS should be scheduled for later.
        """
        # Check company setting
        try:
            settings = company.settings
            if not settings.respect_sms_template_time_window:
                return None
        except Exception:
            return None

        if not template.send_start_time or not template.send_end_time:
            return None

        now = timezone.localtime(timezone.now())
        current_time = now.time()

        start = template.send_start_time
        end = template.send_end_time

        # If current time is within the window, no delay needed
        if start <= current_time <= end:
            return None

        # If before the window start today, schedule for today at start
        if current_time < start:
            send_at = now.replace(
                hour=start.hour, minute=start.minute, second=0, microsecond=0
            )
            return send_at

        # If after the window end, schedule for tomorrow at start
        from datetime import timedelta
        tomorrow = now + timedelta(days=1)
        send_at = tomorrow.replace(
            hour=start.hour, minute=start.minute, second=0, microsecond=0
        )
        return send_at


# =============================================================================
# SMS QUEUE FROM TEMPLATE SERVICE
# =============================================================================


class SMSQueueFromTemplateService:
    """
    Look up template, render message, calculate schedule, deduplicate, and queue.
    This is the primary entry point for template-based SMS sending.
    """

    @staticmethod
    def queue_from_template(
        *,
        company,
        template_key: str,
        phone_number: str,
        context: dict,
        fallback_message: str = "",
        order_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
    ) -> Optional[SMSOutbox]:
        """
        Queue an SMS from a template.

        1. Look up active template by (company, key).
        2. Render template text with context.
        3. Calculate send_at based on time window.
        4. Deduplicate: skip if identical pending SMS exists.
        5. Queue the SMS.

        Falls back to fallback_message if no template is active.
        Returns None if no message could be queued.
        """
        if not phone_number:
            return None

        try:
            from apps.notifications.services import NotificationSettingService
            if not NotificationSettingService.is_sms_enabled(
                company=company,
                event_key=str(template_key),
            ):
                return None
        except Exception:
            # Notification settings must never break the primary workflow.
            pass

        template = SMSTemplate.objects.filter(
            company=company, key=template_key, is_active=True
        ).first()

        if template:
            message = SMSTemplateRenderService.render(
                template_text=template.template_text, context=context
            )
            send_at = SMSTimeWindowService.calculate_send_at(
                template=template, company=company
            )
        else:
            if not fallback_message:
                return None
            message = fallback_message
            send_at = None
            template = None

        # Deduplicate: skip if same company + phone + template_key + order_id is pending
        existing = SMSOutbox.objects.filter(
            company=company,
            phone_number=phone_number,
            template_key=template_key,
            status=SMSOutbox.Status.PENDING,
        )
        if order_id:
            existing = existing.filter(order_id=order_id)
        if invoice_id:
            existing = existing.filter(invoice_id=invoice_id)
        if existing.exists():
            return existing.first()

        return SMSQueueService.queue(
            company=company,
            phone_number=phone_number,
            message=message,
            template=template,
            template_key=template_key,
            send_at=send_at,
            order_id=order_id,
            invoice_id=invoice_id,
        )


# =============================================================================
# SMS EVENT HOOKS
# =============================================================================


class SMSEventHooks:
    """
    Event hooks for triggering SMS from other services.
    Called AFTER primary operations succeed.

    Uses template-based approach with fallback messages.
    IMPORTANT: Only sends if company has active SMS provider or template.
    """

    @staticmethod
    def on_order_created(*, order) -> Optional[SMSOutbox]:
        """Send SMS to customer about new order."""
        if not (order.customer and order.customer.phone):
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_CREATED_ADMIN,
            phone_number=order.customer.phone,
            context=context,
            fallback_message=f"Your service request #{order.id} has been registered.",
            order_id=order.id,
        )

    @staticmethod
    def on_order_assigned_technician(*, order) -> Optional[SMSOutbox]:
        """Send SMS to technician about assignment."""
        tech_phone = ""
        if order.technician and order.technician.user:
            tech_phone = getattr(order.technician.user, "phone", "") or ""
        if not tech_phone:
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_ASSIGNED_TECHNICIAN,
            phone_number=tech_phone,
            context=context,
            fallback_message=(
                f"\u0633\u0641\u0627\u0631\u0634 #{order.id} \u0628\u0647 \u0634\u0645\u0627 \u062a\u062e\u0635\u06cc\u0635 \u062f\u0627\u062f\u0647 \u0634\u062f. "
                f"\u0645\u0634\u062a\u0631\u06cc: {order.display_customer_name or '-'}"
            ),
            order_id=order.id,
        )

    @staticmethod
    def on_order_accepted(*, order) -> Optional[SMSOutbox]:
        """Send SMS to customer about technician acceptance."""
        if not (order.customer and order.customer.phone):
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_ACCEPTED_CUSTOMER,
            phone_number=order.customer.phone,
            context=context,
            fallback_message=f"A technician has been assigned to your order #{order.id}.",
            order_id=order.id,
        )

    @staticmethod
    def on_order_completed(*, order) -> Optional[SMSOutbox]:
        """Send SMS to customer about order completion."""
        if not (order.customer and order.customer.phone):
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_COMPLETED_CUSTOMER,
            phone_number=order.customer.phone,
            context=context,
            fallback_message=f"Your order #{order.id} has been completed.",
            order_id=order.id,
        )

    @staticmethod
    def on_order_cancel_requested_admin(*, order, reason: str = "") -> Optional[SMSOutbox]:
        """Send SMS to admin(s) about cancel request."""
        # Notify company phone if available
        company_phone = getattr(order.company, "phone", "") or ""
        if not company_phone:
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        context["reason"] = reason
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_CANCEL_REQUESTED_ADMIN,
            phone_number=company_phone,
            context=context,
            fallback_message=f"\u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0644\u063a\u0648 \u0633\u0641\u0627\u0631\u0634 #{order.id} \u062b\u0628\u062a \u0634\u062f.",
            order_id=order.id,
        )

    @staticmethod
    def on_order_cancel_approved_technician(*, order) -> Optional[SMSOutbox]:
        """Send SMS to technician that cancel was approved."""
        tech_phone = ""
        if order.technician and order.technician.user:
            tech_phone = getattr(order.technician.user, "phone", "") or ""
        if not tech_phone:
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_CANCEL_APPROVED_TECHNICIAN,
            phone_number=tech_phone,
            context=context,
            fallback_message=f"\u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0644\u063a\u0648 \u0633\u0641\u0627\u0631\u0634 #{order.id} \u062a\u0627\u06cc\u06cc\u062f \u0634\u062f.",
            order_id=order.id,
        )

    @staticmethod
    def on_order_cancel_rejected_technician(*, order) -> Optional[SMSOutbox]:
        """Send SMS to technician that cancel was rejected."""
        tech_phone = ""
        if order.technician and order.technician.user:
            tech_phone = getattr(order.technician.user, "phone", "") or ""
        if not tech_phone:
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_CANCEL_REJECTED_TECHNICIAN,
            phone_number=tech_phone,
            context=context,
            fallback_message=f"\u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0644\u063a\u0648 \u0633\u0641\u0627\u0631\u0634 #{order.id} \u0631\u062f \u0634\u062f.",
            order_id=order.id,
        )

    @staticmethod
    def on_invoice_issued(*, invoice) -> Optional[SMSOutbox]:
        """Send SMS to customer about invoice."""
        if not (invoice.customer and invoice.customer.phone):
            return None
        context = SMSTemplateRenderService.build_invoice_context(invoice=invoice)
        return SMSQueueFromTemplateService.queue_from_template(
            company=invoice.company,
            template_key=SMSTemplate.TemplateKey.INVOICE_ISSUED_CUSTOMER,
            phone_number=invoice.customer.phone,
            context=context,
            fallback_message=f"Invoice {getattr(invoice, 'invoice_number', '')} issued. Amount: {getattr(invoice, 'total_amount', 0)}",
            invoice_id=invoice.id,
        )

    @staticmethod
    def on_payment_success(*, invoice) -> Optional[SMSOutbox]:
        """Send SMS to customer about successful payment."""
        if not (invoice.customer and invoice.customer.phone):
            return None
        context = SMSTemplateRenderService.build_invoice_context(invoice=invoice)
        return SMSQueueFromTemplateService.queue_from_template(
            company=invoice.company,
            template_key=SMSTemplate.TemplateKey.PAYMENT_SUCCESS_CUSTOMER,
            phone_number=invoice.customer.phone,
            context=context,
            fallback_message=f"\u067e\u0631\u062f\u0627\u062e\u062a \u0641\u0627\u06a9\u062a\u0648\u0631 {getattr(invoice, 'invoice_number', '')} \u0645\u0648\u0641\u0642 \u0628\u0648\u062f.",
            invoice_id=invoice.id,
        )

    @staticmethod
    def on_payment_failed(*, invoice) -> Optional[SMSOutbox]:
        """Send SMS to customer about failed payment."""
        if not (invoice.customer and invoice.customer.phone):
            return None
        context = SMSTemplateRenderService.build_invoice_context(invoice=invoice)
        return SMSQueueFromTemplateService.queue_from_template(
            company=invoice.company,
            template_key=SMSTemplate.TemplateKey.PAYMENT_FAILED_CUSTOMER,
            phone_number=invoice.customer.phone,
            context=context,
            fallback_message=f"\u067e\u0631\u062f\u0627\u062e\u062a \u0641\u0627\u06a9\u062a\u0648\u0631 {getattr(invoice, 'invoice_number', '')} \u0646\u0627\u0645\u0648\u0641\u0642 \u0628\u0648\u062f.",
            invoice_id=invoice.id,
        )



# =============================================================================
# SMS OUTBOX PROCESSOR SERVICE (Phase 26B)
# =============================================================================


class SMSOutboxProcessorService:
    """
    Process pending SMS outbox records and send via provider.

    Selects PENDING records where send_at is null or send_at <= now,
    then attempts to send each via the configured provider.

    Respects tenant isolation and avoids duplicate sends.
    """

    @staticmethod
    def process(
        *,
        company=None,
        limit: int = 100,
        dry_run: bool = False,
    ) -> dict:
        """
        Process due pending SMS messages.

        Args:
            company: Optional company to filter (None = all companies).
            limit: Maximum number of messages to process.
            dry_run: If True, only reports what would be processed.

        Returns:
            dict with keys: scanned, sent, failed, skipped, dry_run
        """
        now = timezone.now()

        from django.db.models import Q

        qs = SMSOutbox.objects.filter(
            status__in=[SMSOutbox.Status.PENDING],
        ).filter(
            Q(send_at__isnull=True) | Q(send_at__lte=now)
        ).select_related("provider", "company").order_by("created_at")

        if company is not None:
            qs = qs.filter(company=company)

        qs = qs[:limit]

        results = {
            "scanned": 0,
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "dry_run": dry_run,
        }

        for sms in qs:
            results["scanned"] += 1

            if dry_run:
                results["skipped"] += 1
                continue

            result = SMSSendService.send(sms=sms)
            if result.status == SMSOutbox.Status.SENT:
                results["sent"] += 1
            elif result.status == SMSOutbox.Status.FAILED:
                results["failed"] += 1
            else:
                results["skipped"] += 1

        return results

    @staticmethod
    def send_single(*, sms: SMSOutbox) -> SMSOutbox:
        """
        Send a single SMS record immediately (manual send/retry).

        Only PENDING or FAILED messages can be sent.
        SENT messages are returned without modification.

        Args:
            sms: The SMSOutbox record to send.

        Returns:
            Updated SMSOutbox record.
        """
        if sms.status == SMSOutbox.Status.SENT:
            return sms

        # Reset status to PENDING for retry of FAILED messages
        if sms.status == SMSOutbox.Status.FAILED:
            sms.status = SMSOutbox.Status.PENDING
            sms.error_message = ""
            sms.save(update_fields=["status", "error_message", "updated_at"])

        return SMSSendService.send(sms=sms)



# =============================================================================
# SMS DIAGNOSTICS SERVICE (Phase 26D)
# =============================================================================


class SMSDiagnosticsService:
    """
    Safe SMS provider diagnostics and test-send.

    Company-scoped. Creates clearly-marked diagnostic outbox rows.
    Does not affect orders or invoices.
    """

    DIAGNOSTIC_TEMPLATE_KEY = "__diagnostic_test__"

    @staticmethod
    def get_provider_info(*, company) -> dict:
        """
        Get summary information about the company's SMS provider configuration.

        Returns:
            Dict with provider info. Does NOT expose API keys or secrets.
            Phase 26F: Includes sending_enabled from SMSSendingSafetyService.
        """
        provider = SMSProviderSelector.get_active_for_company(company=company)
        safety = SMSSendingSafetyService.get_status(company=company)
        if provider is None:
            return {
                "configured": False,
                "provider_name": None,
                "provider_type": None,
                "provider_type_raw": None,
                "sender_number": None,
                "is_test_mode": False,
                "sending_enabled": safety["enabled"],
                "sending_reason": safety["reason"],
            }
        is_test = provider.provider_type == SMSProvider.ProviderType.FAKE
        return {
            "configured": True,
            "provider_name": provider.name,
            "provider_type": provider.get_provider_type_display(),
            "provider_type_raw": provider.provider_type,
            "sender_number": provider.sender_number or "-",
            "is_test_mode": is_test,
            "sending_enabled": safety["enabled"],
            "sending_reason": safety["reason"],
        }

    @staticmethod
    def send_test(
        *,
        company,
        phone_number: str,
        message: str,
        send_immediately: bool = False,
    ) -> dict:
        """
        Create a diagnostic/test SMS outbox row and optionally send it.

        Phone number is validated/normalized before creating the outbox row.
        Invalid numbers return a safe error without creating a row.

        Args:
            company: Tenant company.
            phone_number: Recipient phone number.
            message: Test message content.
            send_immediately: If True, process the outbox row immediately.

        Returns:
            Dict with keys: success, sms (SMSOutbox instance or None), error (str).

        Raises:
            Nothing — errors are returned in the result dict.
        """
        message = (message or "").strip()

        # Phase 26E: Validate and normalize phone number
        is_valid, normalized_phone, phone_error = validate_sms_phone_number(phone_number)
        if not is_valid:
            return {"success": False, "sms": None, "error": phone_error}
        if not message:
            return {"success": False, "sms": None, "error": "متن پیام الزامی است."}

        # Prefix message to make it clearly diagnostic
        diagnostic_message = f"[تست] {message}"

        sms = SMSQueueService.queue(
            company=company,
            phone_number=normalized_phone,
            message=diagnostic_message,
            template_key=SMSDiagnosticsService.DIAGNOSTIC_TEMPLATE_KEY,
        )

        if sms is None:
            return {"success": False, "sms": None, "error": "خطا در ایجاد پیامک تست."}

        if send_immediately:
            sms = SMSOutboxProcessorService.send_single(sms=sms)

        return {"success": True, "sms": sms, "error": ""}
