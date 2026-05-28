"""
Platform Core - Communication Template Views.

Platform owner management views for communication templates.
All views require PLATFORM_OWNER role.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import require_platform_owner

from .models import CommunicationTemplate
from .services_communication import CommunicationTemplateService


@require_platform_owner
def comm_template_list(request: HttpRequest) -> HttpResponse:
    """List all communication templates with filters."""
    templates = CommunicationTemplate.objects.all()

    # Filters
    event_key = request.GET.get("event_key", "")
    channel = request.GET.get("channel", "")
    status = request.GET.get("status", "")

    if event_key:
        templates = templates.filter(event_key=event_key)
    if channel:
        templates = templates.filter(channel=channel)
    if status == "active":
        templates = templates.filter(is_active=True)
    elif status == "inactive":
        templates = templates.filter(is_active=False)

    return render(request, "platform_core/comm_templates/list.html", {
        "templates": templates,
        "event_key_choices": CommunicationTemplate.EventKey.choices,
        "channel_choices": CommunicationTemplate.Channel.choices,
        "filter_event_key": event_key,
        "filter_channel": channel,
        "filter_status": status,
    })


@require_platform_owner
def comm_template_create(request: HttpRequest) -> HttpResponse:
    """GET: show form. POST: create template."""
    errors = {}

    if request.method == "POST":
        event_key = request.POST.get("event_key", "")
        channel = request.POST.get("channel", "")
        recipient_type = request.POST.get("recipient_type", "")
        title_template = request.POST.get("title_template", "").strip()
        body_template = request.POST.get("body_template", "").strip()
        action_label = request.POST.get("action_label", "").strip()
        action_url_template = request.POST.get("action_url_template", "").strip()
        is_active = request.POST.get("is_active") == "on"
        is_required = request.POST.get("is_required") == "on"
        allow_company_toggle = request.POST.get("allow_company_toggle") == "on"

        # Validation
        if not event_key:
            errors["event_key"] = "رویداد الزامی است."
        if not channel:
            errors["channel"] = "کانال الزامی است."
        if not recipient_type:
            errors["recipient_type"] = "نوع گیرنده الزامی است."
        if not title_template:
            errors["title_template"] = "عنوان الزامی است."
        if not body_template:
            errors["body_template"] = "متن پیام الزامی است."

        # Validate placeholders
        if title_template:
            valid, invalid = CommunicationTemplateService.validate_placeholders(title_template)
            if not valid:
                errors["title_template"] = f"متغیرهای نامعتبر: {', '.join(invalid)}"
        if body_template:
            valid, invalid = CommunicationTemplateService.validate_placeholders(body_template)
            if not valid:
                errors["body_template"] = f"متغیرهای نامعتبر: {', '.join(invalid)}"

        # Validate URL
        if action_url_template and not CommunicationTemplateService.validate_action_url(action_url_template):
            errors["action_url_template"] = "آدرس لینک نامعتبر است (لینک‌های مطلق مجاز نیستند)."

        if not errors:
            CommunicationTemplate.objects.create(
                event_key=event_key,
                channel=channel,
                recipient_type=recipient_type,
                title_template=title_template,
                body_template=body_template,
                action_label=action_label,
                action_url_template=action_url_template,
                is_active=is_active,
                is_required=is_required,
                allow_company_toggle=allow_company_toggle,
            )
            return redirect("platform_core:comm_templates")

        # Re-render form with errors
        return render(request, "platform_core/comm_templates/form.html", {
            "is_edit": False,
            "errors": errors,
            "form_data": request.POST,
            "event_key_choices": CommunicationTemplate.EventKey.choices,
            "channel_choices": CommunicationTemplate.Channel.choices,
            "recipient_type_choices": CommunicationTemplate.RecipientType.choices,
        })

    return render(request, "platform_core/comm_templates/form.html", {
        "is_edit": False,
        "errors": {},
        "form_data": {},
        "event_key_choices": CommunicationTemplate.EventKey.choices,
        "channel_choices": CommunicationTemplate.Channel.choices,
        "recipient_type_choices": CommunicationTemplate.RecipientType.choices,
    })


@require_platform_owner
def comm_template_edit(request: HttpRequest, template_id: int) -> HttpResponse:
    """GET: show form with existing data. POST: update template."""
    template = get_object_or_404(CommunicationTemplate, pk=template_id)
    errors = {}

    if request.method == "POST":
        event_key = request.POST.get("event_key", "")
        channel = request.POST.get("channel", "")
        recipient_type = request.POST.get("recipient_type", "")
        title_template = request.POST.get("title_template", "").strip()
        body_template = request.POST.get("body_template", "").strip()
        action_label = request.POST.get("action_label", "").strip()
        action_url_template = request.POST.get("action_url_template", "").strip()
        is_active = request.POST.get("is_active") == "on"
        is_required = request.POST.get("is_required") == "on"
        allow_company_toggle = request.POST.get("allow_company_toggle") == "on"

        # Validation
        if not event_key:
            errors["event_key"] = "رویداد الزامی است."
        if not channel:
            errors["channel"] = "کانال الزامی است."
        if not recipient_type:
            errors["recipient_type"] = "نوع گیرنده الزامی است."
        if not title_template:
            errors["title_template"] = "عنوان الزامی است."
        if not body_template:
            errors["body_template"] = "متن پیام الزامی است."

        # Validate placeholders
        if title_template:
            valid, invalid = CommunicationTemplateService.validate_placeholders(title_template)
            if not valid:
                errors["title_template"] = f"متغیرهای نامعتبر: {', '.join(invalid)}"
        if body_template:
            valid, invalid = CommunicationTemplateService.validate_placeholders(body_template)
            if not valid:
                errors["body_template"] = f"متغیرهای نامعتبر: {', '.join(invalid)}"

        # Validate URL
        if action_url_template and not CommunicationTemplateService.validate_action_url(action_url_template):
            errors["action_url_template"] = "آدرس لینک نامعتبر است (لینک‌های مطلق مجاز نیستند)."

        if not errors:
            template.event_key = event_key
            template.channel = channel
            template.recipient_type = recipient_type
            template.title_template = title_template
            template.body_template = body_template
            template.action_label = action_label
            template.action_url_template = action_url_template
            template.is_active = is_active
            template.is_required = is_required
            template.allow_company_toggle = allow_company_toggle
            template.save()
            return redirect("platform_core:comm_template_detail", template_id=template.pk)

        # Re-render form with errors
        return render(request, "platform_core/comm_templates/form.html", {
            "is_edit": True,
            "template": template,
            "errors": errors,
            "form_data": request.POST,
            "event_key_choices": CommunicationTemplate.EventKey.choices,
            "channel_choices": CommunicationTemplate.Channel.choices,
            "recipient_type_choices": CommunicationTemplate.RecipientType.choices,
        })

    # GET: pre-fill with existing data
    form_data = {
        "event_key": template.event_key,
        "channel": template.channel,
        "recipient_type": template.recipient_type,
        "title_template": template.title_template,
        "body_template": template.body_template,
        "action_label": template.action_label,
        "action_url_template": template.action_url_template,
        "is_active": template.is_active,
        "is_required": template.is_required,
        "allow_company_toggle": template.allow_company_toggle,
    }
    return render(request, "platform_core/comm_templates/form.html", {
        "is_edit": True,
        "template": template,
        "errors": {},
        "form_data": form_data,
        "event_key_choices": CommunicationTemplate.EventKey.choices,
        "channel_choices": CommunicationTemplate.Channel.choices,
        "recipient_type_choices": CommunicationTemplate.RecipientType.choices,
    })


@require_platform_owner
def comm_template_detail(request: HttpRequest, template_id: int) -> HttpResponse:
    """Show template details with rendered preview."""
    template = get_object_or_404(CommunicationTemplate, pk=template_id)

    # Sample context for preview
    sample_context = {
        "company_name": "شرکت نمونه",
        "company_code": "sample-co",
        "operator_name": "علی محمدی",
        "technician_name": "رضا احمدی",
        "order_id": "1234",
        "order_status": "در حال انجام",
        "invoice_id": "INV-5678",
        "invoice_amount": "۱,۵۰۰,۰۰۰",
        "payment_status": "پرداخت شده",
        "sms_balance": "۵۰,۰۰۰",
        "sms_remaining_count": "96",
        "tracking_code": "TRK-9876",
    }

    preview = CommunicationTemplateService.render_template(template, sample_context)

    return render(request, "platform_core/comm_templates/detail.html", {
        "template": template,
        "preview": preview,
    })
