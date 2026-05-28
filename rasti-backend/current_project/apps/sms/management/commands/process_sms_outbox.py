"""
Management command: process_sms_outbox

Process pending SMS outbox records and send them via configured providers.

Usage:
    python manage.py process_sms_outbox
    python manage.py process_sms_outbox --company-code n54
    python manage.py process_sms_outbox --limit 50
    python manage.py process_sms_outbox --dry-run
"""
from django.core.management.base import BaseCommand, CommandError

from apps.sms.services import SMSOutboxProcessorService
from apps.tenants.models import Company


class Command(BaseCommand):
    help = "Process pending SMS outbox records and send via configured providers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-code",
            type=str,
            default=None,
            help="Process only this company's SMS (e.g. n54). If omitted, all companies are processed.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of messages to process (default: 100).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be processed without actually sending.",
        )

    def handle(self, *args, **options):
        company_code = options["company_code"]
        limit = options["limit"]
        dry_run = options["dry_run"]

        company = None
        if company_code:
            company = Company.objects.filter(code=company_code).first()
            if not company:
                raise CommandError(f"Company with code '{company_code}' not found.")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE — no messages will be sent.\n"))

        results = SMSOutboxProcessorService.process(
            company=company,
            limit=limit,
            dry_run=dry_run,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"SMS Outbox Processing Complete:\n"
                f"  Scanned:  {results['scanned']}\n"
                f"  Sent:     {results['sent']}\n"
                f"  Failed:   {results['failed']}\n"
                f"  Skipped:  {results['skipped']}\n"
                f"  Dry Run:  {results['dry_run']}"
            )
        )
