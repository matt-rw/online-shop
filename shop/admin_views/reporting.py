"""
Admin views for scheduled reports management.
"""
import json

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

import pytz


@csrf_exempt
def scheduled_reports_dashboard(request):
    """
    Dashboard for managing scheduled reports.
    """
    from shop.models import ScheduledReport, ScheduledReportLog
    from shop.utils.report_generator import ReportGenerator

    chicago_tz = pytz.timezone("America/Chicago")

    # Handle AJAX requests
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        action = request.POST.get("action") or request.GET.get("action")

        # Parse JSON body if present
        if not action and request.content_type == "application/json":
            try:
                body_data = json.loads(request.body)
                action = body_data.get("action")
            except (json.JSONDecodeError, ValueError):
                body_data = {}
        else:
            body_data = {}

        if action == "save_report":
            try:
                if request.content_type == "application/json":
                    data = body_data
                else:
                    data = request.POST

                report_id = data.get("id")

                # Parse send_time
                send_time_str = data.get("send_time", "09:00")
                try:
                    from datetime import datetime
                    send_time = datetime.strptime(send_time_str, "%H:%M").time()
                except ValueError:
                    send_time = datetime.strptime("09:00", "%H:%M").time()

                # Get selected metrics
                selected_metrics = data.get("selected_metrics", [])
                if isinstance(selected_metrics, str):
                    selected_metrics = json.loads(selected_metrics)

                report_data = {
                    "name": data.get("name", "").strip(),
                    "status": data.get("status", "active"),
                    "frequency": data.get("frequency", "daily"),
                    "send_time": send_time,
                    "weekly_day": int(data.get("weekly_day", 0)),
                    "delivery_method": data.get("delivery_method", "email"),
                    "email_recipients": data.get("email_recipients", "").strip(),
                    "sms_recipients": data.get("sms_recipients", "").strip(),
                    "selected_metrics": selected_metrics,
                    "include_comparison": data.get("include_comparison", True),
                }

                if isinstance(report_data["include_comparison"], str):
                    report_data["include_comparison"] = report_data["include_comparison"].lower() == "true"

                if report_id:
                    # Update existing
                    report = ScheduledReport.objects.get(id=report_id)
                    for key, value in report_data.items():
                        setattr(report, key, value)
                    # Recalculate next send time
                    report.next_scheduled_at = report.calculate_next_send_time()
                    report.save()
                    message = "Report updated successfully"
                else:
                    # Create new
                    report = ScheduledReport.objects.create(**report_data)
                    message = "Report created successfully"

                return JsonResponse({
                    "success": True,
                    "message": message,
                    "report_id": report.id,
                })

            except ScheduledReport.DoesNotExist:
                return JsonResponse({"success": False, "error": "Report not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "delete_report":
            try:
                data = body_data if body_data else json.loads(request.body)
                report_id = data.get("id")
                ScheduledReport.objects.filter(id=report_id).delete()
                return JsonResponse({"success": True, "message": "Report deleted"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "toggle_status":
            try:
                data = body_data if body_data else json.loads(request.body)
                report_id = data.get("id")
                report = ScheduledReport.objects.get(id=report_id)

                if report.status == "active":
                    report.status = "paused"
                else:
                    report.status = "active"
                    # Recalculate next send time when resuming
                    report.next_scheduled_at = report.calculate_next_send_time()

                report.save()
                return JsonResponse({
                    "success": True,
                    "status": report.status,
                    "message": f"Report {'paused' if report.status == 'paused' else 'resumed'}"
                })
            except ScheduledReport.DoesNotExist:
                return JsonResponse({"success": False, "error": "Report not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "send_now":
            try:
                from shop.utils.email_helper import send_email
                from shop.utils.sms_helper import send_sms

                data = body_data if body_data else json.loads(request.body)
                report_id = data.get("id")
                report = ScheduledReport.objects.get(id=report_id)

                # Generate metrics
                generator = ReportGenerator(frequency=report.frequency)
                metrics_data = generator.calculate_all_metrics(
                    selected_metrics=report.selected_metrics if report.selected_metrics else None
                )

                # Create log entry
                log = ScheduledReportLog.objects.create(
                    report=report,
                    status="pending",
                    period_start=generator.period_start,
                    period_end=timezone.now(),
                    comparison_period_start=generator.comparison_start,
                    comparison_period_end=generator.comparison_end,
                    report_data=metrics_data,
                )

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
                        try:
                            success, _ = send_email(
                                email_address=email_address,
                                subject=f"{report.name} - {report.get_frequency_display()} Report",
                                html_body=html_content,
                            )
                            if success:
                                email_sent += 1
                            else:
                                email_failed += 1
                        except Exception as e:
                            email_failed += 1
                            errors.append(str(e))

                # Send SMS
                if report.delivery_method in ("sms", "both"):
                    sms_recipients = report.get_sms_recipients_list()
                    sms_content = generator.format_for_sms(metrics_data, report.name)

                    for phone_number in sms_recipients:
                        try:
                            success, _ = send_sms(
                                phone_number=phone_number,
                                message=sms_content,
                            )
                            if success:
                                sms_sent += 1
                            else:
                                sms_failed += 1
                        except Exception as e:
                            sms_failed += 1
                            errors.append(str(e))

                # Update log
                log.email_sent = email_sent
                log.email_failed = email_failed
                log.sms_sent = sms_sent
                log.sms_failed = sms_failed
                log.error_message = "\n".join(errors) if errors else ""
                log.completed_at = timezone.now()

                total_success = email_sent + sms_sent
                total_fail = email_failed + sms_failed

                if total_fail == 0 and total_success > 0:
                    log.status = "sent"
                elif total_success > 0 and total_fail > 0:
                    log.status = "partial"
                else:
                    log.status = "failed"

                log.save()

                # Update report stats
                report.last_sent_at = timezone.now()
                report.total_sends += 1
                if log.status == "failed":
                    report.failed_sends += 1
                report.save()

                return JsonResponse({
                    "success": True,
                    "message": f"Report sent! {total_success} delivered, {total_fail} failed",
                    "email_sent": email_sent,
                    "sms_sent": sms_sent,
                })

            except ScheduledReport.DoesNotExist:
                return JsonResponse({"success": False, "error": "Report not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "preview_report":
            try:
                data = body_data if body_data else json.loads(request.body)

                # Get parameters from request
                frequency = data.get("frequency", "daily")
                selected_metrics = data.get("selected_metrics", [])
                report_name = data.get("name", "Preview Report")

                # Generate metrics
                generator = ReportGenerator(frequency=frequency)
                metrics_data = generator.calculate_all_metrics(
                    selected_metrics=selected_metrics if selected_metrics else None
                )

                # Format as email for preview
                html_preview = generator.format_for_email(metrics_data, report_name)
                sms_preview = generator.format_for_sms(metrics_data, report_name)

                return JsonResponse({
                    "success": True,
                    "html_preview": html_preview,
                    "sms_preview": sms_preview,
                    "metrics_data": metrics_data,
                })

            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "get_report":
            try:
                report_id = request.GET.get("id") or (body_data.get("id") if body_data else None)
                report = ScheduledReport.objects.get(id=report_id)

                return JsonResponse({
                    "success": True,
                    "report": {
                        "id": report.id,
                        "name": report.name,
                        "status": report.status,
                        "frequency": report.frequency,
                        "send_time": report.send_time.strftime("%H:%M"),
                        "weekly_day": report.weekly_day,
                        "delivery_method": report.delivery_method,
                        "email_recipients": report.email_recipients,
                        "sms_recipients": report.sms_recipients,
                        "selected_metrics": report.selected_metrics,
                        "include_comparison": report.include_comparison,
                    }
                })
            except ScheduledReport.DoesNotExist:
                return JsonResponse({"success": False, "error": "Report not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        return JsonResponse({"success": False, "error": "Unknown action"})

    # Regular page load
    reports = ScheduledReport.objects.all().order_by("-created_at")

    # Stats
    stats = {
        "total": reports.count(),
        "active": reports.filter(status="active").count(),
        "paused": reports.filter(status="paused").count(),
        "total_sends": sum(r.total_sends for r in reports),
        "total_failures": sum(r.failed_sends for r in reports),
    }

    # Recent logs
    recent_logs = ScheduledReportLog.objects.select_related("report").order_by("-created_at")[:20]

    # Get metric definitions for the form
    metric_definitions = ReportGenerator.get_available_metrics()

    # Prepare reports data for template
    reports_data = []
    for report in reports:
        next_send_chicago = None
        if report.next_scheduled_at:
            next_send_chicago = report.next_scheduled_at.astimezone(chicago_tz)

        last_sent_chicago = None
        if report.last_sent_at:
            last_sent_chicago = report.last_sent_at.astimezone(chicago_tz)

        reports_data.append({
            "id": report.id,
            "name": report.name,
            "status": report.status,
            "status_display": report.get_status_display(),
            "frequency": report.frequency,
            "frequency_display": report.get_frequency_display(),
            "send_time": report.send_time.strftime("%H:%M"),
            "weekly_day": report.weekly_day,
            "weekly_day_display": report.get_weekly_day_display(),
            "delivery_method": report.delivery_method,
            "delivery_method_display": report.get_delivery_method_display(),
            "email_recipients": report.email_recipients,
            "sms_recipients": report.sms_recipients,
            "selected_metrics": report.selected_metrics,
            "include_comparison": report.include_comparison,
            "next_scheduled_at": next_send_chicago,
            "last_sent_at": last_sent_chicago,
            "total_sends": report.total_sends,
            "failed_sends": report.failed_sends,
        })

    context = {
        "reports": reports_data,
        "stats": stats,
        "recent_logs": recent_logs,
        "metric_definitions": metric_definitions,
        "cst_time": timezone.now().astimezone(chicago_tz),
    }

    return render(request, "admin/scheduled_reports_dashboard.html", context)
