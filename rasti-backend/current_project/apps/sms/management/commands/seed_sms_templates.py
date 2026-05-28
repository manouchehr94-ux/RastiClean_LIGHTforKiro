"""
Management command: seed_sms_templates

Creates default SMS templates for all active companies.
Skips templates that already exist (idempotent).
"""
from django.core.management.base import BaseCommand

from apps.sms.models import SMSTemplate
from apps.tenants.models import Company

DEFAULT_TEMPLATES = [
    {
        "key": SMSTemplate.TemplateKey.ORDER_CREATED_ADMIN,
        "title": "سفارش جدید - مدیر",
        "template_text": "سفارش جدید #{{ order_id }} توسط {{ customer_name }} ثبت شد.",
    },
    {
        "key": SMSTemplate.TemplateKey.ORDER_AVAILABLE_TECHNICIAN,
        "title": "سفارش جدید - تکنسین",
        "template_text": "سفارش جدید #{{ order_id }} در رسته {{ service_title }} برای شما قابل مشاهده است.",
    },
    {
        "key": SMSTemplate.TemplateKey.ORDER_ASSIGNED_TECHNICIAN,
        "title": "تخصیص سفارش - تکنسین",
        "template_text": "سفارش #{{ order_id }} به شما تخصیص داده شد. مشتری: {{ customer_name }}",
    },
    {
        "key": SMSTemplate.TemplateKey.ORDER_ACCEPTED_CUSTOMER,
        "title": "قبول سفارش - مشتری",
        "template_text": "{{ customer_name }} عزیز، تکنسین {{ technician_name }} سفارش #{{ order_id }} شما را پذیرفت.",
    },
    {
        "key": SMSTemplate.TemplateKey.ORDER_COMPLETED_CUSTOMER,
        "title": "اتمام سفارش - مشتری",
        "template_text": "{{ customer_name }} عزیز، سفارش #{{ order_id }} شما تکمیل شد.",
    },
    {
        "key": SMSTemplate.TemplateKey.ORDER_CANCEL_REQUESTED_ADMIN,
        "title": "درخواست لغو - مدیر",
        "template_text": "تکنسین {{ technician_name }} درخواست لغو سفارش #{{ order_id }} را ثبت کرد.",
    },
    {
        "key": SMSTemplate.TemplateKey.ORDER_CANCEL_APPROVED_TECHNICIAN,
        "title": "تایید لغو - تکنسین",
        "template_text": "درخواست لغو سفارش #{{ order_id }} تایید شد.",
    },
    {
        "key": SMSTemplate.TemplateKey.ORDER_CANCEL_REJECTED_TECHNICIAN,
        "title": "رد لغو - تکنسین",
        "template_text": "درخواست لغو سفارش #{{ order_id }} رد شد. لطفا ادامه دهید.",
    },
    {
        "key": SMSTemplate.TemplateKey.INVOICE_ISSUED_CUSTOMER,
        "title": "صدور فاکتور - مشتری",
        "template_text": "{{ customer_name }} عزیز، فاکتور {{ invoice_number }} به مبلغ {{ total_amount }} ریال صادر شد.",
    },
    {
        "key": SMSTemplate.TemplateKey.PAYMENT_SUCCESS_CUSTOMER,
        "title": "پرداخت موفق - مشتری",
        "template_text": "{{ customer_name }} عزیز، پرداخت فاکتور {{ invoice_number }} با موفقیت انجام شد.",
    },
    {
        "key": SMSTemplate.TemplateKey.PAYMENT_FAILED_CUSTOMER,
        "title": "پرداخت ناموفق - مشتری",
        "template_text": "{{ customer_name }} عزیز، پرداخت فاکتور {{ invoice_number }} ناموفق بود. لطفا مجددا تلاش کنید.",
    },
    {
        "key": SMSTemplate.TemplateKey.SURVEY_REQUEST_CUSTOMER,
        "title": "نظرسنجی - مشتری",
        "template_text": "{{ customer_name }} عزیز، لطفا نظر خود را درباره سفارش #{{ order_id }} ثبت کنید.",
    },
]


class Command(BaseCommand):
    help = "Seed default SMS templates for all active companies."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-code",
            type=str,
            default="",
            help="Seed only for a specific company code.",
        )

    def handle(self, *args, **options):
        company_code = options["company_code"]
        if company_code:
            companies = Company.objects.filter(code=company_code, is_active=True)
        else:
            companies = Company.objects.filter(is_active=True)

        created_count = 0
        for company in companies:
            for tpl_data in DEFAULT_TEMPLATES:
                _, created = SMSTemplate.objects.get_or_create(
                    company=company,
                    key=tpl_data["key"],
                    defaults={
                        "title": tpl_data["title"],
                        "template_text": tpl_data["template_text"],
                        "is_active": True,
                    },
                )
                if created:
                    created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created_count} templates across {companies.count()} companies."
            )
        )
