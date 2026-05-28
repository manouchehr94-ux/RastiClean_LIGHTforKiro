"""
Tenant Admin - Communication Settings View.

Tenant admins can ONLY toggle templates that Platform Owner allows.
They CANNOT edit text, title, body, links, or placeholders.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.permissions import require_tenant_role

from .models import CommunicationTemplate, CommunicationTemplateCompanySetting
from .services_communication import CommunicationTemplateService


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def communication_settings(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Tenant admin communication settings page.
    Shows toggleable templates for this company.
    """
    company = request.company

    if request.method == "POST":
        # Process toggle submissions
        template_id = request.POST.get("template_id")
        action = request.POST.get("action")

        if template_id and action in ("enable", "disable"):
            tpl = CommunicationTemplate.objects.filter(
                id=template_id,
                is_active=True,
                allow_company_toggle=True,
                is_required=False,
            ).first()

            if tpl:
                setting, _ = CommunicationTemplateCompanySetting.objects.get_or_create(
                    company=company,
                    template=tpl,
                    defaults={"updated_by": request.user},
                )
                setting.is_enabled = (action == "enable")
                setting.updated_by = request.user
                setting.save(update_fields=["is_enabled", "updated_by", "updated_at"])

        return redirect(f"/{company.code}/admin/communication-settings/")

    # GET - show all toggleable templates
    templates_data = CommunicationTemplateService.get_all_for_company(company=company)

    return render(request, "tenants/admin_communication_settings.html", {
        "company": company,
        "templates_data": templates_data,
    })
