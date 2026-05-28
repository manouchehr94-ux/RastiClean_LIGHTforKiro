"""
SMS - Views.

Admin views for SMS outbox and template management.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import require_tenant_role

from .models import SMSTemplate
from .selectors import SMSOutboxSelector


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_outbox_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """Admin view of SMS outbox for the company."""
    company = request.company
    messages = SMSOutboxSelector.get_for_company(company=company)
    return render(request, "sms/outbox_list.html", {
        "messages": messages,
        "company": company,
    })


def _sync_templates_from_notification_settings(*, company) -> None:
    try:
        from apps.notifications.models import NotificationSetting
        from apps.notifications.services import NotificationSettingService
    except Exception:
        return

    NotificationSettingService.ensure_defaults(company=company)
    settings_by_key = {
        row.event_key: row
        for row in NotificationSetting.objects.filter(company=company)
    }

    for template in SMSTemplate.objects.filter(company=company):
        setting = settings_by_key.get(template.key)
        if setting is None:
            continue
        if template.is_active != setting.sms_enabled:
            template.is_active = setting.sms_enabled
            template.save(update_fields=["is_active", "updated_at"])


def _sync_notification_setting_from_template(*, template: SMSTemplate) -> None:
    try:
        from apps.notifications.models import NotificationSetting
        from apps.notifications.services import NotificationSettingService
    except Exception:
        return

    NotificationSettingService.ensure_defaults(company=template.company)
    setting = NotificationSetting.objects.filter(
        company=template.company,
        event_key=template.key,
    ).first()
    if setting is None:
        return

    if setting.sms_enabled != template.is_active:
        setting.sms_enabled = template.is_active
        setting.save(update_fields=["sms_enabled", "updated_at"])


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_template_list(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    _sync_templates_from_notification_settings(company=company)
    templates = SMSTemplate.objects.filter(company=company)
    return render(request, "sms/template_list.html", {
        "templates": templates,
        "company": company,
    })


@require_tenant_role("COMPANY_ADMIN")
def sms_template_create(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    if request.method == "POST":
        key = request.POST.get("key", "")
        title = request.POST.get("title", "")
        template_text = request.POST.get("template_text", "")
        is_active = request.POST.get("is_active") == "on"
        send_start_time = request.POST.get("send_start_time") or None
        send_end_time = request.POST.get("send_end_time") or None

        template = SMSTemplate.objects.create(
            company=company,
            key=key,
            title=title,
            template_text=template_text,
            is_active=is_active,
            send_start_time=send_start_time,
            send_end_time=send_end_time,
        )
        _sync_notification_setting_from_template(template=template)
        return redirect(f"/{company.code}/admin/sms/templates/")

    key_choices = SMSTemplate.TemplateKey.choices
    return render(request, "sms/template_form.html", {
        "company": company,
        "key_choices": key_choices,
        "template": None,
        "editing": False,
    })


@require_tenant_role("COMPANY_ADMIN")
def sms_template_edit(request: HttpRequest, pk: int, **kwargs) -> HttpResponse:
    company = request.company
    template = get_object_or_404(SMSTemplate, pk=pk, company=company)

    if request.method == "POST":
        template.title = request.POST.get("title", template.title)
        template.template_text = request.POST.get("template_text", template.template_text)
        template.is_active = request.POST.get("is_active") == "on"
        template.send_start_time = request.POST.get("send_start_time") or None
        template.send_end_time = request.POST.get("send_end_time") or None
        template.save()
        _sync_notification_setting_from_template(template=template)
        return redirect(f"/{company.code}/admin/sms/templates/")

    key_choices = SMSTemplate.TemplateKey.choices
    return render(request, "sms/template_form.html", {
        "company": company,
        "key_choices": key_choices,
        "template": template,
        "editing": True,
    })


@require_tenant_role("COMPANY_ADMIN")
def sms_template_toggle(request: HttpRequest, pk: int, **kwargs) -> HttpResponse:
    company = request.company
    template = get_object_or_404(SMSTemplate, pk=pk, company=company)
    template.is_active = not template.is_active
    template.save(update_fields=["is_active", "updated_at"])
    _sync_notification_setting_from_template(template=template)
    return redirect(f"/{company.code}/admin/sms/templates/")



# =============================================================================
# SMS OUTBOX ADMIN (Phase 26B + 26C)
# =============================================================================

PAGE_SIZE = 50


def _build_filter_query_string(*, status_filter: str, template_key_filter: str, search_q: str) -> str:
    """Build query string from active filters (for pagination links)."""
    from urllib.parse import urlencode
    params = {}
    if status_filter:
        params["status"] = status_filter
    if template_key_filter:
        params["template_key"] = template_key_filter
    if search_q:
        params["q"] = search_q
    return urlencode(params)


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_outbox_admin_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Admin view of SMS outbox with filtering and pagination.

    Filters:
    - status: pending, sent, failed, cancelled
    - template_key: filter by template key
    - q: search by phone number

    Pagination:
    - page: page number (default 1)
    - page_size: 50 (fixed)
    """
    from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

    from .models import SMSOutbox, SMSTemplate

    company = request.company
    status_filter = request.GET.get("status", "").strip()
    template_key_filter = request.GET.get("template_key", "").strip()
    search_q = request.GET.get("q", "").strip()

    qs = SMSOutbox.objects.filter(company=company).select_related(
        "template", "provider"
    ).order_by("-created_at")

    if status_filter:
        qs = qs.filter(status=status_filter)
    if template_key_filter:
        qs = qs.filter(template_key=template_key_filter)
    if search_q:
        qs = qs.filter(phone_number__icontains=search_q)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", "1")
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    filter_qs = _build_filter_query_string(
        status_filter=status_filter,
        template_key_filter=template_key_filter,
        search_q=search_q,
    )

    return render(request, "sms/outbox_admin_list.html", {
        "company": company,
        "page_obj": page_obj,
        "messages": page_obj.object_list,
        "status_filter": status_filter,
        "template_key_filter": template_key_filter,
        "search_q": search_q,
        "status_choices": SMSOutbox.Status.choices,
        "template_key_choices": SMSTemplate.TemplateKey.choices,
        "filter_qs": filter_qs,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_outbox_send_now(request: HttpRequest, pk: int, **kwargs) -> HttpResponse:
    """
    Manual send/retry for a single SMS outbox record.

    POST-only. Only PENDING or FAILED messages can be sent.
    SENT messages are not resent.
    """
    from django.http import HttpResponseForbidden

    if request.method != "POST":
        return HttpResponseForbidden("POST only.")

    from .models import SMSOutbox
    from .services import SMSOutboxProcessorService

    company = request.company
    sms = get_object_or_404(SMSOutbox, pk=pk, company=company)

    if sms.status == SMSOutbox.Status.SENT:
        return redirect(f"/{company.code}/admin/sms/outbox/")

    SMSOutboxProcessorService.send_single(sms=sms)
    return redirect(f"/{company.code}/admin/sms/outbox/")


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_outbox_bulk_retry(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Bulk retry/send for multiple SMS outbox records.

    POST-only. Processes selected IDs that are PENDING or FAILED.
    SENT rows are skipped. Cross-company rows are ignored.
    """
    from django.http import HttpResponseForbidden

    if request.method != "POST":
        return HttpResponseForbidden("POST only.")

    from .models import SMSOutbox
    from .services import SMSOutboxProcessorService

    company = request.company
    selected_ids = request.POST.getlist("selected_ids")

    sent = 0
    failed = 0
    skipped = 0

    if selected_ids:
        # Only process IDs that belong to this company and are retryable
        sms_qs = SMSOutbox.objects.filter(
            pk__in=selected_ids,
            company=company,
        )
        for sms in sms_qs:
            if sms.status == SMSOutbox.Status.SENT:
                skipped += 1
                continue
            if sms.status in (SMSOutbox.Status.PENDING, SMSOutbox.Status.FAILED):
                result = SMSOutboxProcessorService.send_single(sms=sms)
                if result.status == SMSOutbox.Status.SENT:
                    sent += 1
                else:
                    failed += 1
            else:
                skipped += 1

    # Redirect back preserving filters if present
    redirect_url = f"/{company.code}/admin/sms/outbox/"
    # Pass summary via query params (simple approach, no messages framework needed)
    from urllib.parse import urlencode
    summary_params = urlencode({
        "bulk_sent": sent,
        "bulk_failed": failed,
        "bulk_skipped": skipped,
    })
    return redirect(f"{redirect_url}?{summary_params}")



# =============================================================================
# SMS DIAGNOSTICS (Phase 26D)
# =============================================================================


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_diagnostics(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    SMS provider diagnostics and safe test-send page.

    GET: Show provider info and test-send form.
    POST: Create a diagnostic outbox row and optionally send immediately.
    """
    from .services import SMSDiagnosticsService

    company = request.company
    provider_info = SMSDiagnosticsService.get_provider_info(company=company)

    result = None
    error = ""

    if request.method == "POST":
        phone_number = request.POST.get("phone_number", "").strip()
        message = request.POST.get("message", "").strip()
        send_immediately = bool(request.POST.get("send_immediately"))

        send_result = SMSDiagnosticsService.send_test(
            company=company,
            phone_number=phone_number,
            message=message,
            send_immediately=send_immediately,
        )

        if send_result["success"]:
            result = send_result["sms"]
        else:
            error = send_result["error"]

    return render(request, "sms/diagnostics.html", {
        "company": company,
        "provider_info": provider_info,
        "result": result,
        "error": error,
    })
