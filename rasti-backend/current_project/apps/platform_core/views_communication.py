"""
Platform Core - Communication Template Management Views.

Platform Owner can:
- List all templates
- Create/edit template text, title, body, flags
- Set is_required / allow_company_toggle

No real SMS/email delivery — templates define intent only.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import require_platform_owner

from .models import CommunicationTemplate


@require_platform_owner
def template_list(request: HttpRequest) -> HttpResponse:
    """List all communication templates."""
    templates = CommunicationTemplate.objects.all()
    return render(request, "platform_core/communication/list.html", {
        "templates": templates,
    })


@require_platform_owner
def template_create(request: HttpRequest) -> HttpResponse:
    """Create a new communication template."""
    if request.method == "POST":
        CommunicationTemplate.objects.create(
            event_key=request.POST.get("event_key", "").strip(),
            channel=request.POST.get("channel", "IN_APP"),
            recipient_type=request.POST.get("recipient_type", "COMPANY_ADMIN"),
            title=request.POST.get("title", "").strip(),
            body=request.POST.get("body", "").strip(),
            action_label=request.POST.get("action_label", "").strip(),
            action_url_template=request.POST.get("action_url_template", "").strip(),
            allowed_placeholders=request.POST.get("allowed_placeholders", "").strip(),
            is_active=request.POST.get("is_active") == "on",
            is_required=request.POST.get("is_required") == "on",
            allow_company_toggle=request.POST.get("allow_company_toggle") == "on",
        )
        return redirect("platform_core:comm_templates")

    return render(request, "platform_core/communication/form.html", {
        "is_edit": False,
        "tpl": None,
    })


@require_platform_owner
def template_edit(request: HttpRequest, template_id: int) -> HttpResponse:
    """Edit an existing communication template."""
    tpl = get_object_or_404(CommunicationTemplate, id=template_id)

    if request.method == "POST":
        tpl.event_key = request.POST.get("event_key", "").strip()
        tpl.channel = request.POST.get("channel", "IN_APP")
        tpl.recipient_type = request.POST.get("recipient_type", "COMPANY_ADMIN")
        tpl.title = request.POST.get("title", "").strip()
        tpl.body = request.POST.get("body", "").strip()
        tpl.action_label = request.POST.get("action_label", "").strip()
        tpl.action_url_template = request.POST.get("action_url_template", "").strip()
        tpl.allowed_placeholders = request.POST.get("allowed_placeholders", "").strip()
        tpl.is_active = request.POST.get("is_active") == "on"
        tpl.is_required = request.POST.get("is_required") == "on"
        tpl.allow_company_toggle = request.POST.get("allow_company_toggle") == "on"
        tpl.save()
        return redirect("platform_core:comm_templates")

    return render(request, "platform_core/communication/form.html", {
        "is_edit": True,
        "tpl": tpl,
    })
