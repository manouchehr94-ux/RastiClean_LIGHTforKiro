"""
Platform Core - Tenant Communication Settings Views.

Views for tenant company admins to toggle communication templates.
They can only enable/disable templates — they cannot edit content.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.permissions import require_tenant_role

from .models import CommunicationTemplateCompanySetting
from .services_communication import CommunicationTemplateService


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_comm_settings(request: HttpRequest, **kwargs) -> HttpResponse:
    """GET: show toggleable templates. POST: toggle a template."""
    company = request.company
    success = ""

    if request.method == "POST":
        template_id = request.POST.get("template_id")
        action = request.POST.get("action")  # "enable" or "disable"

        if template_id and action in ("enable", "disable"):
            from .models import CommunicationTemplate
            try:
                tpl = CommunicationTemplate.objects.get(pk=template_id, is_active=True)
                if tpl.allow_company_toggle and not tpl.is_required:
                    setting, created = CommunicationTemplateCompanySetting.objects.get_or_create(
                        company=company,
                        template=tpl,
                        defaults={"is_enabled": action == "enable", "updated_by": request.user},
                    )
                    if not created:
                        setting.is_enabled = (action == "enable")
                        setting.updated_by = request.user
                        setting.save()
                    success = "تنظیمات ذخیره شد."
            except CommunicationTemplate.DoesNotExist:
                pass

    templates_data = CommunicationTemplateService.get_all_for_company(company)

    return render(request, "tenants/admin_comm_settings.html", {
        "company": company,
        "templates_data": templates_data,
        "success": success,
    })
