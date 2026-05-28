"""
Platform Core - Communication Template Resolution Service.

Resolution order:
1. Template is_active=False → globally disabled, skip
2. Template is_required=True → always use, ignore company toggle
3. Template allow_company_toggle=True → check company setting
4. Company setting is_enabled=False → skip for that company
5. Otherwise → use template

No real SMS/email delivery. This service only resolves WHICH templates
should be active for a given company + event. Delivery is a future concern.
"""
from typing import Optional

from apps.tenants.models import Company

from .models import CommunicationTemplate, CommunicationTemplateCompanySetting


class CommunicationTemplateService:
    """Resolves active templates for a company/event combination."""

    @staticmethod
    def is_template_active_for_company(
        *, template: CommunicationTemplate, company: Company
    ) -> bool:
        """
        Determine if a template should be used for a given company.

        Resolution:
        1. Globally inactive → False
        2. Required → True (cannot be disabled)
        3. Company toggle allowed → check setting
        4. No setting exists → default True (active)
        """
        if not template.is_active:
            return False

        if template.is_required:
            return True

        if not template.allow_company_toggle:
            return True

        # Check company-specific setting
        setting = CommunicationTemplateCompanySetting.objects.filter(
            company=company, template=template
        ).first()

        if setting is None:
            # No override → default active
            return True

        return setting.is_enabled

    @staticmethod
    def get_active_template(
        *, event_key: str, channel: str, recipient_type: str, company: Company
    ) -> Optional[CommunicationTemplate]:
        """
        Get the active template for a specific event/channel/recipient/company.

        Returns None if no active template exists or if disabled for this company.
        """
        template = CommunicationTemplate.objects.filter(
            event_key=event_key,
            channel=channel,
            recipient_type=recipient_type,
        ).first()

        if template is None:
            return None

        if not CommunicationTemplateService.is_template_active_for_company(
            template=template, company=company
        ):
            return None

        return template

    @staticmethod
    def get_all_for_company(*, company: Company) -> list[dict]:
        """
        Get all templates with their resolved status for a company.
        Used by tenant admin communication settings page.

        Returns list of dicts with template info + resolved is_active status.
        """
        templates = CommunicationTemplate.objects.filter(
            is_active=True, allow_company_toggle=True
        )

        result = []
        for tpl in templates:
            setting = CommunicationTemplateCompanySetting.objects.filter(
                company=company, template=tpl
            ).first()

            result.append({
                "template": tpl,
                "is_enabled": setting.is_enabled if setting else True,
                "is_required": tpl.is_required,
                "can_toggle": tpl.allow_company_toggle and not tpl.is_required,
            })

        return result
