"""
Django management command to process and send scheduled reports.
Run via cron every minute: * * * * * python manage.py send_scheduled_reports
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process and send scheduled reports that are due"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force send even if not yet scheduled",
        )
        parser.add_argument(
            "--report-id",
            type=int,
            help="Send a specific report by ID (ignores schedule)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be sent without actually sending",
        )

    def handle(self, *args, **options):
        from shop.models import ScheduledReport, ScheduledReportLog
        from shop.utils.report_generator import ReportGenerator
        from shop.utils.email_helper import send_email
        from shop.utils.sms_helper import send_sms

        now = timezone.now()
        force = options.get("force", False)
        report_id = options.get("report_id")
        dry_run = options.get("dry_run", False)

        self.stdout.write(
            self.style.SUCCESS(f"\n=== Processing Scheduled Reports at {now} ===\n")
        )

        # Get reports to process
        if report_id:
            reports = ScheduledReport.objects.filter(id=report_id)
            if not reports.exists():
                self.stdout.write(
                    self.style.ERROR(f"Report with ID {report_id} not found")
                )
                return
            self.stdout.write(f"Processing specific report: {report_id}")
        elif force:
            reports = ScheduledReport.objects.filter(status="active")
            self.stdout.write("Force mode: processing all active reports")
        else:
            # Normal mode: get reports that are due
            reports = ScheduledReport.objects.filter(
                status="active",
                next_scheduled_at__lte=now
            )

        report_count = reports.count()
        self.stdout.write(f"Found {report_count} report(s) to process\n")

        if report_count == 0:
            return

        total_sent = 0
        total_failed = 0

        for report in reports:
            self.stdout.write(f"\n--- Processing: {report.name} ---")
            self.stdout.write(f"    Frequency: {report.get_frequency_display()}")
            self.stdout.write(f"    Delivery: {report.get_delivery_method_display()}")

            if dry_run:
                self.stdout.write(self.style.WARNING("    [DRY RUN] Would send report"))
                continue

            # Create log entry
            log = ScheduledReportLog.objects.create(
                report=report,
                status="pending"
            )

            try:
                # Generate metrics
                generator = ReportGenerator(frequency=report.frequency)
                metrics_data = generator.calculate_all_metrics(
                    selected_metrics=report.selected_metrics if report.selected_metrics else None
                )

                # Store period info in log
                log.period_start = generator.period_start
                log.period_end = now
                log.comparison_period_start = generator.comparison_start
                log.comparison_period_end = generator.comparison_end
                log.report_data = metrics_data

                # Track delivery results
                email_sent = 0
                email_failed = 0
                sms_sent = 0
                sms_failed = 0
                errors = []

                # Send emails
                if report.delivery_method in ("email", "both"):
                    email_recipients = report.get_email_recipients_list()
                    html_content = generator.format_for_email(metrics_data, report.name)

                    for email_address in email_recipients:
                        self.stdout.write(f"    Sending email to: {email_address}")
                        try:
                            success, email_log = send_email(
                                email_address=email_address,
                                subject=f"{report.name} - {report.get_frequency_display()} Report",
                                html_body=html_content,
                            )
                            if success:
                                email_sent += 1
                                self.stdout.write(
                                    self.style.SUCCESS(f"      ✓ Sent")
                                )
                            else:
                                email_failed += 1
                                errors.append(f"Email to {email_address}: {email_log.error_message}")
                                self.stdout.write(
                                    self.style.ERROR(f"      ✗ Failed: {email_log.error_message}")
                                )
                        except Exception as e:
                            email_failed += 1
                            errors.append(f"Email to {email_address}: {str(e)}")
                            self.stdout.write(
                                self.style.ERROR(f"      ✗ Error: {str(e)}")
                            )

                # Send SMS
                if report.delivery_method in ("sms", "both"):
                    sms_recipients = report.get_sms_recipients_list()
                    sms_content = generator.format_for_sms(metrics_data, report.name)

                    for phone_number in sms_recipients:
                        self.stdout.write(f"    Sending SMS to: {phone_number}")
                        try:
                            success, sms_log = send_sms(
                                phone_number=phone_number,
                                message=sms_content,
                            )
                            if success:
                                sms_sent += 1
                                self.stdout.write(
                                    self.style.SUCCESS(f"      ✓ Sent")
                                )
                            else:
                                sms_failed += 1
                                errors.append(f"SMS to {phone_number}: {sms_log.error_message}")
                                self.stdout.write(
                                    self.style.ERROR(f"      ✗ Failed: {sms_log.error_message}")
                                )
                        except Exception as e:
                            sms_failed += 1
                            errors.append(f"SMS to {phone_number}: {str(e)}")
                            self.stdout.write(
                                self.style.ERROR(f"      ✗ Error: {str(e)}")
                            )

                # Update log
                log.email_sent = email_sent
                log.email_failed = email_failed
                log.sms_sent = sms_sent
                log.sms_failed = sms_failed
                log.error_message = "\n".join(errors) if errors else ""
                log.completed_at = timezone.now()

                # Determine overall status
                total_success = email_sent + sms_sent
                total_fail = email_failed + sms_failed

                if total_fail == 0 and total_success > 0:
                    log.status = "sent"
                elif total_success > 0 and total_fail > 0:
                    log.status = "partial"
                elif total_success == 0:
                    log.status = "failed"
                else:
                    log.status = "sent"

                log.save()

                # Update report
                report.last_sent_at = now
                report.next_scheduled_at = report.calculate_next_send_time(from_time=now)
                report.total_sends += 1
                if log.status == "failed":
                    report.failed_sends += 1
                report.save()

                total_sent += total_success
                total_failed += total_fail

                self.stdout.write(
                    f"    Result: {total_success} sent, {total_fail} failed"
                )
                self.stdout.write(
                    f"    Next scheduled: {report.next_scheduled_at}"
                )

            except Exception as e:
                logger.exception(f"Error processing report {report.id}: {str(e)}")
                log.status = "failed"
                log.error_message = str(e)
                log.completed_at = timezone.now()
                log.save()

                report.failed_sends += 1
                report.save()

                total_failed += 1

                self.stdout.write(
                    self.style.ERROR(f"    ✗ Error: {str(e)}")
                )

        # Summary
        self.stdout.write(self.style.SUCCESS("\n=== Summary ==="))
        self.stdout.write(f"Reports processed: {report_count}")
        self.stdout.write(f"Total messages sent: {total_sent}")
        self.stdout.write(f"Total messages failed: {total_failed}")
        self.stdout.write(self.style.SUCCESS("\nDone!\n"))
