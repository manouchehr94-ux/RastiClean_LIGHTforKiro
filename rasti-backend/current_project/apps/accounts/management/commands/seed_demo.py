"""
Management command: seed demo data for local development.

Usage:
    python manage.py seed_demo
    python manage.py seed_demo --reset --confirm

Creates:
    - platform_owner / password123 (PLATFORM_OWNER, is_staff, is_superuser)
    - Company: n54 + CompanySettings + CompanyPage
    - n54_admin / password123 (COMPANY_ADMIN, company=n54)
    - n54_tech / password123 (TECHNICIAN, company=n54) + Technician profile
    - n54_operator / password123 (COMPANY_STAFF, company=n54) + OperatorPermissions
    - Service category + 2 subcategories
    - 2 Orders (new, in_progress)
    - 1 Invoice with 2 items
    - SMS pricing + wallet
    - Payment gateway settings (MOCK)
    - Communication templates (via seed_communication_templates logic)

Flags:
    --reset     Delete all demo data before re-seeding (requires --confirm)
    --confirm   Confirm destructive reset operation
"""
from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.accounts.models import (
    CompanyUser,
    Customer,
    OperatorPermission,
    Technician,
    UserRole,
)
from apps.invoices.models import Invoice, InvoiceItem, generate_invoice_number
from apps.orders.models import Order
from apps.platform_core.models import (
    CompanyPaymentGatewaySetting,
    CompanySMSWallet,
    GlobalSMSPricingSetting,
    PaymentGatewayProvider,
    PlatformPaymentGatewaySetting,
)
from apps.tenants.models import (
    Company,
    CompanyPage,
    CompanyServiceCategory,
    CompanyServiceSubCategory,
    CompanySettings,
)


class Command(BaseCommand):
    help = "Seed demo company and users for local development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all demo data before re-seeding.",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm destructive reset operation.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            if not options["confirm"]:
                self.stderr.write(
                    self.style.ERROR(
                        "WARNING: --reset will delete ALL demo data.\n"
                        "  Add --confirm to proceed: python manage.py seed_demo --reset --confirm"
                    )
                )
                return
            self.stdout.write(self.style.WARNING("Resetting demo data..."))
            self.reset_demo()

        self.stdout.write(self.style.MIGRATE_HEADING("Seeding demo data..."))
        self.stdout.write("")

        # 1. Platform owner user
        platform_owner = self._create_platform_owner()

        # 2. Company n54 + settings + page
        company = self._create_company()

        # 3. Admin user
        admin_user = self._create_admin(company)

        # 4. Tech user + Technician profile
        tech_user, technician = self._create_technician(company)

        # 5. Operator user + permissions
        operator_user = self._create_operator(company)

        # 6. Service category + subcategories
        category, subcategories = self._create_service_categories(company)

        # 7. Customer
        customer = self._create_customer(company)

        # 8. Orders
        orders = self._create_orders(company, customer, technician, category, subcategories)

        # 9. Invoice
        invoice = self._create_invoice(company, customer, orders[1])

        # 10. SMS pricing + wallet
        self._create_sms_settings(company, platform_owner)

        # 11. Payment gateway settings
        self._create_payment_gateway_settings(company, platform_owner)

        # 12. Communication templates
        self.stdout.write("  Seeding communication templates...")
        call_command("seed_communication_templates", stdout=self.stdout)

        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Demo data seeded successfully!"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write("")
        self.stdout.write("  Credentials (all use password: password123):")
        self.stdout.write(f"    platform_owner  - Platform Owner (superuser)")
        self.stdout.write(f"    n54_admin       - Company Admin (company=n54)")
        self.stdout.write(f"    n54_tech        - Technician (company=n54)")
        self.stdout.write(f"    n54_operator    - Operator/Staff (company=n54)")
        self.stdout.write("")
        self.stdout.write("  URLs:")
        self.stdout.write("    Platform admin: /loginlogin/")
        self.stdout.write("    Company admin:  /n54/admin/")
        self.stdout.write("    Tech panel:     /n54/tech/")
        self.stdout.write("")

    def reset_demo(self):
        """Delete all demo data for company n54 and platform_owner."""
        # Delete company cascades to orders, invoices, notifications, etc.
        Company.objects.filter(code="n54").delete()
        # Delete demo users (platform_owner has no company)
        CompanyUser.objects.filter(
            username__in=["platform_owner", "n54_admin", "n54_tech", "n54_operator"]
        ).delete()
        # Delete global SMS pricing (singleton)
        GlobalSMSPricingSetting.objects.all().delete()
        # Delete platform payment gateway setting
        PlatformPaymentGatewaySetting.objects.all().delete()
        self.stdout.write("  Demo data deleted.")
        self.stdout.write("")

    # ─── Seed helpers ────────────────────────────────────────────────

    def _create_platform_owner(self) -> CompanyUser:
        user, created = CompanyUser.objects.get_or_create(
            username="platform_owner",
            defaults={
                "phone": "09100000001",
                "role": UserRole.PLATFORM_OWNER,
                "company": None,
                "first_name": "\u0645\u062f\u06cc\u0631",
                "last_name": "\u067e\u0644\u062a\u0641\u0631\u0645",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password("password123")
            user.save()
            self.stdout.write("  Created user: platform_owner (PLATFORM_OWNER)")
        else:
            self.stdout.write("  Exists: platform_owner")
        return user

    def _create_company(self) -> Company:
        company, created = Company.objects.get_or_create(
            code="n54",
            defaults={
                "name": "\u0634\u0631\u06a9\u062a \u0646\u0645\u0648\u0646\u0647 \u06f5\u06f4",
                "slug": "n54",
                "is_active": True,
                "phone": "02112345678",
                "email": "info@n54.ir",
                "address": "\u062a\u0647\u0631\u0627\u0646\u060c \u062e\u06cc\u0627\u0628\u0627\u0646 \u0622\u0632\u0627\u062f\u06cc\u060c \u067e\u0644\u0627\u06a9 \u06f1\u06f2",
            },
        )
        if created:
            self.stdout.write(f"  Created company: {company.name} ({company.code})")
        else:
            self.stdout.write(f"  Exists: company {company.code}")

        # Settings
        CompanySettings.objects.get_or_create(
            company=company,
            defaults={
                "priority2_delay_minutes": 30,
                "priority3_delay_minutes": 60,
                "max_active_orders_per_technician": 5,
            },
        )

        # Page
        CompanyPage.objects.get_or_create(
            company=company,
            defaults={
                "title": company.name,
                "intro_text": "\u0627\u0631\u0627\u0626\u0647\u200c\u062f\u0647\u0646\u062f\u0647 \u062e\u062f\u0645\u0627\u062a \u0646\u0638\u0627\u0641\u062a \u0648 \u0646\u0638\u0627\u0641\u062a \u0635\u0646\u0639\u062a\u06cc",
                "contact_phone": "02112345678",
                "contact_email": "info@n54.ir",
                "working_hours": "\u0634\u0646\u0628\u0647 \u062a\u0627 \u067e\u0646\u062c\u0634\u0646\u0628\u0647 \u06f9:\u06f0\u06f0-\u06f1\u06f8:\u06f0\u06f0",
                "is_published": True,
                "is_request_form_enabled": True,
            },
        )

        return company

    def _create_admin(self, company: Company) -> CompanyUser:
        user, created = CompanyUser.objects.get_or_create(
            username="n54_admin",
            defaults={
                "phone": "09100000002",
                "role": UserRole.COMPANY_ADMIN,
                "company": company,
                "first_name": "\u0645\u062f\u06cc\u0631",
                "last_name": "\u0634\u0631\u06a9\u062a",
            },
        )
        if created:
            user.set_password("password123")
            user.save()
            self.stdout.write("  Created user: n54_admin (COMPANY_ADMIN)")
        else:
            self.stdout.write("  Exists: n54_admin")
        return user

    def _create_technician(self, company: Company) -> tuple[CompanyUser, Technician]:
        user, created = CompanyUser.objects.get_or_create(
            username="n54_tech",
            defaults={
                "phone": "09100000003",
                "role": UserRole.TECHNICIAN,
                "company": company,
                "first_name": "\u0639\u0644\u06cc",
                "last_name": "\u062a\u06a9\u0646\u0633\u06cc\u0646",
            },
        )
        if created:
            user.set_password("password123")
            user.save()
            self.stdout.write("  Created user: n54_tech (TECHNICIAN)")
        else:
            self.stdout.write("  Exists: n54_tech")

        technician, _ = Technician.objects.get_or_create(
            user=user,
            defaults={
                "company": company,
                "national_id": "0012345678",
                "is_available": True,
                "rating": Decimal("4.50"),
                "notes": "\u062a\u06a9\u0646\u0633\u06cc\u0646 \u0646\u0645\u0648\u0646\u0647 \u0628\u0631\u0627\u06cc \u062a\u0633\u062a",
            },
        )
        return user, technician

    def _create_operator(self, company: Company) -> CompanyUser:
        user, created = CompanyUser.objects.get_or_create(
            username="n54_operator",
            defaults={
                "phone": "09100000004",
                "role": UserRole.COMPANY_STAFF,
                "company": company,
                "first_name": "\u0627\u067e\u0631\u0627\u062a\u0648\u0631",
                "last_name": "\u0646\u0645\u0648\u0646\u0647",
            },
        )
        if created:
            user.set_password("password123")
            user.save()
            self.stdout.write("  Created user: n54_operator (COMPANY_STAFF)")
        else:
            self.stdout.write("  Exists: n54_operator")

        # Operator permissions
        permission_keys = [
            "orders_list",
            "orders_detail",
            "orders_create",
            "customers_list",
            "invoices_list",
            "invoices_create",
        ]
        for key in permission_keys:
            OperatorPermission.objects.get_or_create(
                company=company,
                operator=user,
                permission_key=key,
                defaults={"is_allowed": True},
            )
        self.stdout.write(f"  Operator permissions: {len(permission_keys)} keys set")

        return user

    def _create_service_categories(
        self, company: Company
    ) -> tuple[CompanyServiceCategory, list[CompanyServiceSubCategory]]:
        category, _ = CompanyServiceCategory.objects.get_or_create(
            company=company,
            title="\u0646\u0638\u0627\u0641\u062a \u0645\u0646\u0632\u0644",
            defaults={
                "description": "\u062e\u062f\u0645\u0627\u062a \u0646\u0638\u0627\u0641\u062a \u0648 \u0634\u0633\u062a\u0634\u0648\u06cc \u0645\u0646\u0632\u0644",
                "is_active": True,
                "sort_order": 1,
            },
        )
        self.stdout.write(f"  Service category: {category.title}")

        sub1, _ = CompanyServiceSubCategory.objects.get_or_create(
            company=company,
            category=category,
            title="\u0646\u0638\u0627\u0641\u062a \u0639\u0645\u0648\u0645\u06cc",
            defaults={
                "description": "\u0646\u0638\u0627\u0641\u062a \u06a9\u0627\u0645\u0644 \u0645\u0646\u0632\u0644",
                "base_price": Decimal("1500000"),
                "is_active": True,
                "sort_order": 1,
            },
        )

        sub2, _ = CompanyServiceSubCategory.objects.get_or_create(
            company=company,
            category=category,
            title="\u0634\u0633\u062a\u0634\u0648\u06cc \u0641\u0631\u0634",
            defaults={
                "description": "\u0634\u0633\u062a\u0634\u0648\u06cc \u0641\u0631\u0634 \u062f\u0631 \u0645\u0646\u0632\u0644",
                "base_price": Decimal("800000"),
                "is_active": True,
                "sort_order": 2,
            },
        )

        self.stdout.write(f"  Subcategories: {sub1.title}, {sub2.title}")
        return category, [sub1, sub2]

    def _create_customer(self, company: Company) -> Customer:
        customer, created = Customer.objects.get_or_create(
            company=company,
            phone="09121234567",
            defaults={
                "first_name": "\u0631\u0636\u0627",
                "last_name": "\u0645\u0634\u062a\u0631\u06cc",
                "email": "reza@example.com",
                "address": "\u062a\u0647\u0631\u0627\u0646\u060c \u0633\u0639\u0627\u062f\u062a\u200c\u0622\u0628\u0627\u062f\u060c \u0628\u0644\u0648\u0627\u0631 \u0627\u0635\u0644\u06cc",
            },
        )
        if created:
            self.stdout.write(f"  Created customer: {customer.first_name} {customer.last_name}")
        else:
            self.stdout.write(f"  Exists: customer {customer.phone}")
        return customer

    def _create_orders(
        self,
        company: Company,
        customer: Customer,
        technician: Technician,
        category: CompanyServiceCategory,
        subcategories: list[CompanyServiceSubCategory],
    ) -> list[Order]:
        order1, created1 = Order.objects.get_or_create(
            company=company,
            title="\u0646\u0638\u0627\u0641\u062a \u0639\u0645\u0648\u0645\u06cc \u0645\u0646\u0632\u0644",
            customer=customer,
            status=Order.Status.NEW,
            defaults={
                "customer_name": "\u0631\u0636\u0627 \u0645\u0634\u062a\u0631\u06cc",
                "customer_phone": "09121234567",
                "description": "\u0646\u0638\u0627\u0641\u062a \u06a9\u0627\u0645\u0644 \u0622\u067e\u0627\u0631\u062a\u0645\u0627\u0646 \u06f1\u06f2\u06f0 \u0645\u062a\u0631\u06cc",
                "address": "\u062a\u0647\u0631\u0627\u0646\u060c \u0633\u0639\u0627\u062f\u062a\u200c\u0622\u0628\u0627\u062f\u060c \u0628\u0644\u0648\u0627\u0631 \u0627\u0635\u0644\u06cc\u060c \u067e\u0644\u0627\u06a9 \u06f8",
                "service_date": date(2025, 6, 15),
                "service_category": category,
                "service_subcategory": subcategories[0] if subcategories else None,
                "priority": Order.Priority.NORMAL,
                "price_estimate": Decimal("1500000"),
            },
        )

        order2, created2 = Order.objects.get_or_create(
            company=company,
            title="\u0634\u0633\u062a\u0634\u0648\u06cc \u0641\u0631\u0634 \u06f3 \u062a\u062e\u062a\u0647",
            customer=customer,
            status=Order.Status.IN_PROGRESS,
            defaults={
                "customer_name": "\u0631\u0636\u0627 \u0645\u0634\u062a\u0631\u06cc",
                "customer_phone": "09121234567",
                "technician": technician,
                "description": "\u0634\u0633\u062a\u0634\u0648\u06cc \u06f3 \u062a\u062e\u062a\u0647 \u0641\u0631\u0634 \u06f6 \u0645\u062a\u0631\u06cc",
                "address": "\u062a\u0647\u0631\u0627\u0646\u060c \u0633\u0639\u0627\u062f\u062a\u200c\u0622\u0628\u0627\u062f\u060c \u0628\u0644\u0648\u0627\u0631 \u0627\u0635\u0644\u06cc\u060c \u067e\u0644\u0627\u06a9 \u06f8",
                "service_date": date(2025, 6, 10),
                "service_category": category,
                "service_subcategory": subcategories[1] if len(subcategories) > 1 else None,
                "priority": Order.Priority.HIGH,
                "price_estimate": Decimal("2400000"),
                "final_price": Decimal("2400000"),
            },
        )

        count = sum([created1, created2])
        self.stdout.write(f"  Orders: {count} created, {2 - count} existed")
        return [order1, order2]

    def _create_invoice(
        self, company: Company, customer: Customer, order: Order
    ) -> Invoice:
        # Check if an invoice already exists for this order
        existing = Invoice.objects.filter(company=company, order=order).first()
        if existing:
            self.stdout.write(f"  Exists: invoice {existing.invoice_number}")
            return existing

        invoice_number = generate_invoice_number(company)
        invoice = Invoice.objects.create(
            company=company,
            order=order,
            customer=customer,
            invoice_number=invoice_number,
            status=Invoice.Status.ISSUED,
            customer_name_snapshot="\u0631\u0636\u0627 \u0645\u0634\u062a\u0631\u06cc",
            customer_phone_snapshot="09121234567",
            address_snapshot="\u062a\u0647\u0631\u0627\u0646\u060c \u0633\u0639\u0627\u062f\u062a\u200c\u0622\u0628\u0627\u062f",
            technician_name_snapshot="\u0639\u0644\u06cc \u062a\u06a9\u0646\u0633\u06cc\u0646",
            technician_phone_snapshot="09100000003",
            service_title_snapshot="\u0634\u0633\u062a\u0634\u0648\u06cc \u0641\u0631\u0634",
            service_date_snapshot=date(2025, 6, 10),
            subtotal=Decimal("2400000"),
            tax_amount=Decimal("216000"),
            discount_amount=Decimal("0"),
            total_amount=Decimal("2616000"),
            notes="\u0641\u0627\u06a9\u062a\u0648\u0631 \u0646\u0645\u0648\u0646\u0647 \u0628\u0631\u0627\u06cc \u062a\u0633\u062a",
        )

        # Invoice items
        InvoiceItem.objects.create(
            company=company,
            invoice=invoice,
            description="\u0634\u0633\u062a\u0634\u0648\u06cc \u0641\u0631\u0634 \u06f6 \u0645\u062a\u0631\u06cc (3 \u062a\u062e\u062a\u0647)",
            quantity=Decimal("3"),
            unit_price=Decimal("800000"),
            discount_amount=Decimal("0"),
            total_price=Decimal("2400000"),
            sort_order=1,
        )
        InvoiceItem.objects.create(
            company=company,
            invoice=invoice,
            description="\u0647\u0632\u06cc\u0646\u0647 \u0627\u06cc\u0627\u0628 \u0648 \u0630\u0647\u0627\u0628",
            quantity=Decimal("1"),
            unit_price=Decimal("0"),
            discount_amount=Decimal("0"),
            total_price=Decimal("0"),
            sort_order=2,
        )

        self.stdout.write(f"  Created invoice: {invoice.invoice_number} (2 items)")
        return invoice

    def _create_sms_settings(self, company: Company, platform_owner: CompanyUser):
        GlobalSMSPricingSetting.objects.update_or_create(
            pk=1,
            defaults={
                "characters_per_sms": 60,
                "price_per_sms_rial": 520,
                "updated_by": platform_owner,
            },
        )
        self.stdout.write("  SMS pricing: 520 rial/sms, 60 chars/sms")

        wallet, _ = CompanySMSWallet.objects.get_or_create(
            company=company,
            defaults={"balance_rial": 50000},
        )
        self.stdout.write(f"  SMS wallet: {wallet.balance_rial} rial")

    def _create_payment_gateway_settings(
        self, company: Company, platform_owner: CompanyUser
    ):
        # Platform gateway
        PlatformPaymentGatewaySetting.objects.update_or_create(
            pk=1,
            defaults={
                "provider": PaymentGatewayProvider.MOCK,
                "is_active": True,
                "merchant_id": "MOCK-PLATFORM-12345",
                "sandbox_mode": True,
                "description": "\u062f\u0631\u06af\u0627\u0647 \u0622\u0632\u0645\u0627\u06cc\u0634\u06cc \u067e\u0644\u062a\u0641\u0631\u0645",
                "updated_by": platform_owner,
            },
        )
        self.stdout.write("  Platform gateway: MOCK (active, sandbox)")

        # Company gateway
        CompanyPaymentGatewaySetting.objects.update_or_create(
            company=company,
            defaults={
                "provider": PaymentGatewayProvider.MOCK,
                "is_active": True,
                "merchant_id": "MOCK-N54-67890",
                "sandbox_mode": True,
                "description": "\u062f\u0631\u06af\u0627\u0647 \u0622\u0632\u0645\u0627\u06cc\u0634\u06cc \u0634\u0631\u06a9\u062a",
                "updated_by": platform_owner,
            },
        )
        self.stdout.write("  Company gateway: MOCK (active, sandbox)")
