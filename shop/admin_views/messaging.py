"""
SMS, email, and campaign management admin views.
"""

import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

import pytz

from shop.models import (
    Campaign,
    CampaignMessage,
    EmailCampaign,
    EmailLog,
    EmailSubscription,
    EmailTemplate,
    SMSCampaign,
    SMSLog,
    SMSSubscription,
    SMSTemplate,
)
from shop.models.messaging import QuickMessage

User = get_user_model()

def sms_dashboard(request):
    """
    SMS Marketing dashboard for managing subscribers, templates, and campaigns.
    Only accessible to admin/staff users.
    """
    from shop.utils.twilio_helper import send_campaign

    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    # Handle campaign send action
    if request.method == "POST" and request.POST.get("action") == "send_campaign":
        campaign_id = request.POST.get("campaign_id")
        try:
            campaign = SMSCampaign.objects.get(id=campaign_id)
            if campaign.status in ["draft", "scheduled"]:
                result = send_campaign(campaign)
                if "error" in result:
                    messages.error(request, f'Campaign failed: {result["error"]}')
                else:
                    messages.success(
                        request,
                        f'Campaign sent! Sent: {result["sent"]}, Failed: {result["failed"]}',
                    )
            else:
                messages.error(request, f"Campaign cannot be sent (status: {campaign.status})")
        except SMSCampaign.DoesNotExist:
            messages.error(request, "Campaign not found")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

        return redirect("admin_sms")

    # SMS Subscription metrics
    total_sms_subs = SMSSubscription.objects.count()
    active_sms_subs = SMSSubscription.objects.filter(is_active=True).count()
    confirmed_sms_subs = SMSSubscription.objects.filter(is_confirmed=True).count()
    recent_sms_subs_24h = SMSSubscription.objects.filter(subscribed_at__gte=last_24h).count()
    recent_sms_subs_7d = SMSSubscription.objects.filter(subscribed_at__gte=last_7d).count()

    sms_metrics = {
        "total": total_sms_subs,
        "active": active_sms_subs,
        "confirmed": confirmed_sms_subs,
        "recent_24h": recent_sms_subs_24h,
        "recent_7d": recent_sms_subs_7d,
        "active_rate": (
            round((active_sms_subs / total_sms_subs * 100), 1) if total_sms_subs > 0 else 0
        ),
    }

    # Templates
    templates = SMSTemplate.objects.all().order_by("-updated_at")
    total_templates = templates.count()
    active_templates = templates.filter(is_active=True).count()

    # Campaigns
    campaigns = SMSCampaign.objects.all().order_by("-created_at")[:10]
    total_campaigns = SMSCampaign.objects.count()

    campaign_stats = {
        "total": total_campaigns,
        "draft": SMSCampaign.objects.filter(status="draft").count(),
        "scheduled": SMSCampaign.objects.filter(status="scheduled").count(),
        "sent": SMSCampaign.objects.filter(status="sent").count(),
    }

    # Recent SMS logs
    recent_logs = SMSLog.objects.select_related("subscription", "campaign", "template").order_by(
        "-sent_at"
    )[:20]

    # SMS stats by status
    total_sms_sent = SMSLog.objects.count()
    sms_delivered = SMSLog.objects.filter(status="delivered").count()
    sms_failed = SMSLog.objects.filter(status="failed").count()
    sms_sent_24h = SMSLog.objects.filter(sent_at__gte=last_24h).count()

    sms_log_stats = {
        "total": total_sms_sent,
        "delivered": sms_delivered,
        "failed": sms_failed,
        "sent_24h": sms_sent_24h,
        "delivery_rate": (
            round((sms_delivered / total_sms_sent * 100), 1) if total_sms_sent > 0 else 0
        ),
    }

    # Recent subscribers
    recent_subscribers = SMSSubscription.objects.order_by("-subscribed_at")[:10]

    # Chart data for subscriber growth (last 30 days)
    subscriber_growth = []
    for i in range(30, -1, -1):
        date = (now - timedelta(days=i)).date()
        count = SMSSubscription.objects.filter(subscribed_at__date=date).count()
        subscriber_growth.append({"date": date.strftime("%m/%d"), "count": count})

    context = {
        "sms_metrics": sms_metrics,
        "templates": templates,
        "total_templates": total_templates,
        "active_templates": active_templates,
        "campaigns": campaigns,
        "campaign_stats": campaign_stats,
        "recent_logs": recent_logs,
        "sms_log_stats": sms_log_stats,
        "recent_subscribers": recent_subscribers,
        "subscriber_growth": subscriber_growth,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/sms_dashboard.html", context)


@staff_member_required
def email_dashboard(request):
    """
    Email Marketing dashboard for managing subscribers, templates, and campaigns.
    Only accessible to admin/staff users.
    """
    from shop.utils.email_helper import send_campaign

    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    # Handle campaign send action
    if request.method == "POST" and request.POST.get("action") == "send_campaign":
        campaign_id = request.POST.get("campaign_id")
        try:
            campaign = EmailCampaign.objects.get(id=campaign_id)
            if campaign.status in ["draft", "scheduled"]:
                result = send_campaign(campaign)
                if "error" in result:
                    messages.error(request, f'Campaign failed: {result["error"]}')
                else:
                    messages.success(
                        request,
                        f'Campaign sent! Sent: {result["sent"]}, Failed: {result["failed"]}',
                    )
            else:
                messages.error(request, f"Campaign cannot be sent (status: {campaign.status})")
        except EmailCampaign.DoesNotExist:
            messages.error(request, "Campaign not found")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

        return redirect("admin_email")

    # Email Subscription metrics
    total_email_subs = EmailSubscription.objects.count()
    active_email_subs = EmailSubscription.objects.filter(is_active=True).count()
    confirmed_email_subs = EmailSubscription.objects.filter(is_confirmed=True).count()
    recent_email_subs_24h = EmailSubscription.objects.filter(subscribed_at__gte=last_24h).count()
    recent_email_subs_7d = EmailSubscription.objects.filter(subscribed_at__gte=last_7d).count()

    email_metrics = {
        "total": total_email_subs,
        "active": active_email_subs,
        "confirmed": confirmed_email_subs,
        "recent_24h": recent_email_subs_24h,
        "recent_7d": recent_email_subs_7d,
        "active_rate": (
            round((active_email_subs / total_email_subs * 100), 1) if total_email_subs > 0 else 0
        ),
    }

    # Templates
    templates = EmailTemplate.objects.all().order_by("-updated_at")
    total_templates = templates.count()
    active_templates = templates.filter(is_active=True).count()

    # Campaigns
    campaigns = EmailCampaign.objects.all().order_by("-created_at")[:10]
    total_campaigns = EmailCampaign.objects.count()

    campaign_stats = {
        "total": total_campaigns,
        "draft": EmailCampaign.objects.filter(status="draft").count(),
        "scheduled": EmailCampaign.objects.filter(status="scheduled").count(),
        "sent": EmailCampaign.objects.filter(status="sent").count(),
    }

    # Recent email logs
    recent_logs = EmailLog.objects.select_related("subscription", "campaign", "template").order_by(
        "-sent_at"
    )[:20]

    # Email stats by status
    total_emails_sent = EmailLog.objects.count()
    emails_delivered = EmailLog.objects.filter(status="delivered").count()
    emails_failed = EmailLog.objects.filter(status="failed").count()
    emails_sent_24h = EmailLog.objects.filter(sent_at__gte=last_24h).count()

    email_log_stats = {
        "total": total_emails_sent,
        "delivered": emails_delivered,
        "failed": emails_failed,
        "sent_24h": emails_sent_24h,
        "delivery_rate": (
            round((emails_delivered / total_emails_sent * 100), 1) if total_emails_sent > 0 else 0
        ),
    }

    # Recent subscribers
    recent_subscribers = EmailSubscription.objects.order_by("-subscribed_at")[:10]

    # Chart data for subscriber growth (last 30 days)
    subscriber_growth = []
    for i in range(30, -1, -1):
        date = (now - timedelta(days=i)).date()
        count = EmailSubscription.objects.filter(subscribed_at__date=date).count()
        subscriber_growth.append({"date": date.strftime("%m/%d"), "count": count})

    context = {
        "email_metrics": email_metrics,
        "templates": templates,
        "total_templates": total_templates,
        "active_templates": active_templates,
        "campaigns": campaigns,
        "campaign_stats": campaign_stats,
        "recent_logs": recent_logs,
        "email_log_stats": email_log_stats,
        "recent_subscribers": recent_subscribers,
        "subscriber_growth": subscriber_growth,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/email_dashboard.html", context)


@staff_member_required
def sms_campaigns(request):
    """
    SMS Campaign management page with create/edit functionality.
    """
    # Handle create/edit
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create":
            name = request.POST.get("name")
            template_id = request.POST.get("template")
            scheduled_at = request.POST.get("scheduled_at")
            notes = request.POST.get("notes", "")

            try:
                template = SMSTemplate.objects.get(id=template_id)
                campaign = SMSCampaign.objects.create(
                    name=name,
                    template=template,
                    scheduled_at=scheduled_at if scheduled_at else None,
                    status="scheduled" if scheduled_at else "draft",
                    notes=notes,
                    created_by=request.user,
                )
                messages.success(request, f'Campaign "{campaign.name}" created successfully!')
                return redirect("admin_sms_campaigns")
            except Exception as e:
                messages.error(request, f"Error creating campaign: {str(e)}")

        elif action == "delete":
            campaign_id = request.POST.get("campaign_id")
            try:
                campaign = SMSCampaign.objects.get(id=campaign_id)
                campaign.delete()
                messages.success(request, "Campaign deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting campaign: {str(e)}")
            return redirect("admin_sms_campaigns")

    # Get all campaigns
    campaigns = SMSCampaign.objects.all().order_by("-created_at")
    templates = SMSTemplate.objects.filter(is_active=True).order_by("name")

    context = {
        "campaigns": campaigns,
        "templates": templates,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/sms_campaigns.html", context)


@staff_member_required
def email_campaigns(request):
    """
    Email Campaign management page with create/edit functionality.
    """
    # Handle create/edit
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create":
            name = request.POST.get("name")
            template_id = request.POST.get("template")
            scheduled_at = request.POST.get("scheduled_at")
            notes = request.POST.get("notes", "")

            try:
                template = EmailTemplate.objects.get(id=template_id)
                campaign = EmailCampaign.objects.create(
                    name=name,
                    template=template,
                    scheduled_at=scheduled_at if scheduled_at else None,
                    status="scheduled" if scheduled_at else "draft",
                    notes=notes,
                    created_by=request.user,
                )
                messages.success(request, f'Campaign "{campaign.name}" created successfully!')
                return redirect("admin_email_campaigns")
            except Exception as e:
                messages.error(request, f"Error creating campaign: {str(e)}")

        elif action == "delete":
            campaign_id = request.POST.get("campaign_id")
            try:
                campaign = EmailCampaign.objects.get(id=campaign_id)
                campaign.delete()
                messages.success(request, "Campaign deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting campaign: {str(e)}")
            return redirect("admin_email_campaigns")

    # Get all campaigns
    campaigns = EmailCampaign.objects.all().order_by("-created_at")
    templates = EmailTemplate.objects.filter(is_active=True).order_by("name")

    context = {
        "campaigns": campaigns,
        "templates": templates,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/email_campaigns.html", context)


def sms_templates(request):
    """
    SMS Template management page with create/edit functionality.
    """
    # Handle create/edit
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create":
            name = request.POST.get("name")
            template_type = request.POST.get("template_type")
            auto_trigger = request.POST.get("auto_trigger")
            message_body = request.POST.get("message_body")
            tags = request.POST.get("tags", "")
            notes = request.POST.get("notes", "")

            try:
                template = SMSTemplate.objects.create(
                    name=name,
                    template_type=template_type,
                    auto_trigger=auto_trigger,
                    message_body=message_body,
                    tags=tags,
                    notes=notes,
                    created_by=request.user,
                )
                messages.success(request, f'Template "{template.name}" created successfully!')
                return redirect("admin_sms_templates")
            except Exception as e:
                messages.error(request, f"Error creating template: {str(e)}")

        elif action == "update":
            template_id = request.POST.get("template_id")
            try:
                template = SMSTemplate.objects.get(id=template_id)
                template.name = request.POST.get("name")
                template.template_type = request.POST.get("template_type")
                template.auto_trigger = request.POST.get("auto_trigger")
                template.message_body = request.POST.get("message_body")
                template.tags = request.POST.get("tags", "")
                template.notes = request.POST.get("notes", "")
                template.is_active = request.POST.get("is_active") == "on"
                template.save()
                messages.success(request, f'Template "{template.name}" updated successfully!')
                return redirect("admin_sms_templates")
            except Exception as e:
                messages.error(request, f"Error updating template: {str(e)}")

        elif action == "delete":
            template_id = request.POST.get("template_id")
            try:
                template = SMSTemplate.objects.get(id=template_id)
                template.delete()
                messages.success(request, "Template deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting template: {str(e)}")
            return redirect("admin_sms_templates")

        elif action == "duplicate":
            template_id = request.POST.get("template_id")
            try:
                original = SMSTemplate.objects.get(id=template_id)
                duplicate = SMSTemplate.objects.create(
                    name=f"Copy of {original.name}",
                    template_type=original.template_type,
                    auto_trigger=original.auto_trigger,
                    message_body=original.message_body,
                    tags=original.tags,
                    notes=original.notes,
                    is_active=False,  # Start as inactive
                    created_by=request.user,
                )
                messages.success(request, f'Template duplicated as "{duplicate.name}"!')
                return redirect("admin_sms_templates")
            except Exception as e:
                messages.error(request, f"Error duplicating template: {str(e)}")
            return redirect("admin_sms_templates")

        elif action == "bulk_activate":
            template_ids = request.POST.getlist("template_ids")
            try:
                count = SMSTemplate.objects.filter(id__in=template_ids).update(is_active=True)
                messages.success(request, f"{count} template(s) activated successfully!")
            except Exception as e:
                messages.error(request, f"Error activating templates: {str(e)}")
            return redirect("admin_sms_templates")

        elif action == "bulk_deactivate":
            template_ids = request.POST.getlist("template_ids")
            try:
                count = SMSTemplate.objects.filter(id__in=template_ids).update(is_active=False)
                messages.success(request, f"{count} template(s) deactivated successfully!")
            except Exception as e:
                messages.error(request, f"Error deactivating templates: {str(e)}")
            return redirect("admin_sms_templates")

        elif action == "bulk_delete":
            template_ids = request.POST.getlist("template_ids")
            try:
                count, _ = SMSTemplate.objects.filter(id__in=template_ids).delete()
                messages.success(request, f"{count} template(s) deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting templates: {str(e)}")
            return redirect("admin_sms_templates")

        elif action == "export":
            template_ids = request.POST.getlist("template_ids")
            if template_ids:
                templates_to_export = SMSTemplate.objects.filter(id__in=template_ids)
            else:
                templates_to_export = SMSTemplate.objects.all()

            data = []
            for template in templates_to_export:
                data.append({
                    "name": template.name,
                    "template_type": template.template_type,
                    "auto_trigger": template.auto_trigger,
                    "message_body": template.message_body,
                    "tags": template.tags,
                    "notes": template.notes,
                    "is_active": template.is_active,
                    "times_used": template.times_used,
                })

            response = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
            response["Content-Disposition"] = f'attachment; filename="sms_templates_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
            return response

    # Get template to edit if specified
    edit_template = None
    template_id = request.GET.get("edit")
    if template_id:
        try:
            edit_template = SMSTemplate.objects.get(id=template_id)
        except SMSTemplate.DoesNotExist:
            messages.error(request, "Template not found")

    # Get all templates with sorting
    sort_by = request.GET.get("sort", "-created_at")
    templates = SMSTemplate.objects.all().order_by(sort_by)

    # Calculate stats
    total_count = templates.count()
    active_count = templates.filter(is_active=True).count()
    inactive_count = total_count - active_count
    total_usage = templates.aggregate(total=Sum('times_used'))['total'] or 0

    # Get all unique tags
    all_tags = set()
    for template in templates:
        if template.tags:
            all_tags.update([tag.strip() for tag in template.tags.split(",")])

    # Serialize templates for JavaScript
    templates_json = json.dumps([
        {
            'id': t.id,
            'name': t.name,
            'template_type': t.template_type,
            'auto_trigger': t.auto_trigger,
            'message_body': t.message_body,
            'is_active': t.is_active,
        }
        for t in templates
    ])

    context = {
        "templates": templates,
        "templates_json": templates_json,
        "edit_template": edit_template,
        "template_types": SMSTemplate.TEMPLATE_TYPES,
        "trigger_types": SMSTemplate.TRIGGER_TYPES,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
        "total_count": total_count,
        "active_count": active_count,
        "inactive_count": inactive_count,
        "total_usage": total_usage,
        "all_tags": sorted(all_tags),
        "current_sort": sort_by,
    }

    return render(request, "admin/sms_templates.html", context)


@staff_member_required
def email_templates(request):
    """
    Email Template management page with create/edit functionality.
    """
    # Handle create/edit
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create":
            name = request.POST.get("name")
            template_type = request.POST.get("template_type")
            folder = request.POST.get("folder", "general")
            auto_trigger = request.POST.get("auto_trigger")
            subject = request.POST.get("subject")
            html_body = request.POST.get("html_body")
            text_body = request.POST.get("text_body", "")
            tags = request.POST.get("tags", "")
            notes = request.POST.get("notes", "")
            design_json_str = request.POST.get("design_json", "")

            # Parse design JSON if provided
            design_json = None
            if design_json_str:
                try:
                    design_json = json.loads(design_json_str)
                except json.JSONDecodeError:
                    pass

            try:
                template = EmailTemplate.objects.create(
                    name=name,
                    template_type=template_type,
                    folder=folder,
                    auto_trigger=auto_trigger,
                    subject=subject,
                    html_body=html_body,
                    text_body=text_body,
                    tags=tags,
                    notes=notes,
                    design_json=design_json,
                    created_by=request.user,
                )
                messages.success(request, f'Template "{template.name}" created successfully!')
                return redirect("admin_email_templates")
            except Exception as e:
                messages.error(request, f"Error creating template: {str(e)}")

        elif action == "update":
            template_id = request.POST.get("template_id")
            try:
                template = EmailTemplate.objects.get(id=template_id)
                template.name = request.POST.get("name")
                template.template_type = request.POST.get("template_type")
                template.folder = request.POST.get("folder", "general")
                template.auto_trigger = request.POST.get("auto_trigger")
                template.subject = request.POST.get("subject")
                template.html_body = request.POST.get("html_body")
                template.text_body = request.POST.get("text_body", "")
                template.tags = request.POST.get("tags", "")
                template.notes = request.POST.get("notes", "")
                template.is_active = request.POST.get("is_active") == "on"

                # Update design JSON if provided
                design_json_str = request.POST.get("design_json", "")
                if design_json_str:
                    try:
                        template.design_json = json.loads(design_json_str)
                    except json.JSONDecodeError:
                        pass

                template.save()
                messages.success(request, f'Template "{template.name}" updated successfully!')
                return redirect("admin_email_templates")
            except Exception as e:
                messages.error(request, f"Error updating template: {str(e)}")

        elif action == "delete":
            template_id = request.POST.get("template_id")
            try:
                template = EmailTemplate.objects.get(id=template_id)
                template.delete()
                messages.success(request, "Template deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting template: {str(e)}")
            return redirect("admin_email_templates")

        elif action == "duplicate":
            template_id = request.POST.get("template_id")
            try:
                original = EmailTemplate.objects.get(id=template_id)
                duplicate = EmailTemplate.objects.create(
                    name=f"Copy of {original.name}",
                    template_type=original.template_type,
                    folder=original.folder,
                    auto_trigger=original.auto_trigger,
                    subject=original.subject,
                    html_body=original.html_body,
                    text_body=original.text_body,
                    design_json=original.design_json,
                    tags=original.tags,
                    notes=original.notes,
                    is_active=False,  # Start as inactive
                    created_by=request.user,
                )
                messages.success(request, f'Template duplicated as "{duplicate.name}"!')
                return redirect("admin_email_templates")
            except Exception as e:
                messages.error(request, f"Error duplicating template: {str(e)}")
            return redirect("admin_email_templates")

        elif action == "bulk_activate":
            template_ids = request.POST.getlist("template_ids")
            try:
                count = EmailTemplate.objects.filter(id__in=template_ids).update(is_active=True)
                messages.success(request, f"{count} template(s) activated successfully!")
            except Exception as e:
                messages.error(request, f"Error activating templates: {str(e)}")
            return redirect("admin_email_templates")

        elif action == "bulk_deactivate":
            template_ids = request.POST.getlist("template_ids")
            try:
                count = EmailTemplate.objects.filter(id__in=template_ids).update(is_active=False)
                messages.success(request, f"{count} template(s) deactivated successfully!")
            except Exception as e:
                messages.error(request, f"Error deactivating templates: {str(e)}")
            return redirect("admin_email_templates")

        elif action == "bulk_delete":
            template_ids = request.POST.getlist("template_ids")
            try:
                count, _ = EmailTemplate.objects.filter(id__in=template_ids).delete()
                messages.success(request, f"{count} template(s) deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting templates: {str(e)}")
            return redirect("admin_email_templates")

        elif action == "add_folder":
            folder_name = request.POST.get("folder_name", "").strip()
            if folder_name:
                # Validate folder name
                if len(folder_name) > 50:
                    messages.error(request, "Folder name is too long (max 50 characters)")
                elif folder_name in dict(EmailTemplate.FOLDER_CHOICES):
                    messages.error(request, f'Folder "{folder_name}" already exists as a default folder')
                else:
                    from shop.models import TemplateFolder
                    # Check if folder already exists
                    if TemplateFolder.objects.filter(name=folder_name).exists():
                        messages.error(request, f'Folder "{folder_name}" already exists')
                    else:
                        TemplateFolder.objects.create(
                            name=folder_name.lower().replace(" ", "_"),
                            display_name=folder_name,
                            created_by=request.user,
                        )
                        messages.success(request, f'Folder "{folder_name}" created successfully!')
            else:
                messages.error(request, "Folder name is required")
            return redirect("admin_email_templates")

        elif action == "delete_folder":
            folder_name = request.POST.get("folder_name")
            from shop.models import TemplateFolder
            try:
                # Move all templates from this folder to general
                templates_in_folder = EmailTemplate.objects.filter(folder=folder_name)
                count = templates_in_folder.update(folder="general")

                # Delete the custom folder
                TemplateFolder.objects.filter(name=folder_name).delete()

                if count > 0:
                    messages.success(request, f'Folder deleted and {count} template(s) moved to General')
                else:
                    messages.success(request, 'Folder deleted successfully!')
            except Exception as e:
                messages.error(request, f"Error deleting folder: {str(e)}")
            return redirect("admin_email_templates")

        elif action == "export":
            template_ids = request.POST.getlist("template_ids")
            if template_ids:
                templates_to_export = EmailTemplate.objects.filter(id__in=template_ids)
            else:
                templates_to_export = EmailTemplate.objects.all()

            data = []
            for template in templates_to_export:
                data.append({
                    "name": template.name,
                    "template_type": template.template_type,
                    "auto_trigger": template.auto_trigger,
                    "subject": template.subject,
                    "html_body": template.html_body,
                    "text_body": template.text_body,
                    "tags": template.tags,
                    "notes": template.notes,
                    "is_active": template.is_active,
                    "times_used": template.times_used,
                })

            response = HttpResponse(json.dumps(data, indent=2), content_type="application/json")
            response["Content-Disposition"] = f'attachment; filename="email_templates_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'
            return response

    # Get template to edit if specified
    edit_template = None
    template_id = request.GET.get("edit")
    if template_id:
        try:
            edit_template = EmailTemplate.objects.get(id=template_id)
        except EmailTemplate.DoesNotExist:
            messages.error(request, "Template not found")

    # Get all templates with sorting
    sort_by = request.GET.get("sort", "-created_at")
    templates = EmailTemplate.objects.all().order_by(sort_by)

    # Calculate stats
    total_count = templates.count()
    active_count = templates.filter(is_active=True).count()
    inactive_count = total_count - active_count
    total_usage = templates.aggregate(total=Sum('times_used'))['total'] or 0

    # Get all unique tags
    all_tags = set()
    for template in templates:
        if template.tags:
            all_tags.update([tag.strip() for tag in template.tags.split(",")])

    # Serialize templates for JavaScript
    templates_json = json.dumps([
        {
            'id': t.id,
            'name': t.name,
            'template_type': t.template_type,
            'auto_trigger': t.auto_trigger,
            'subject': t.subject,
            'html_body': t.html_body,
            'is_active': t.is_active,
        }
        for t in templates
    ])

    # Get folder statistics for default folders
    folder_counts = {}
    for folder_value, folder_label in EmailTemplate.FOLDER_CHOICES:
        count = templates.filter(folder=folder_value).count()
        folder_counts[folder_value] = {'label': folder_label, 'count': count}

    # Add custom folders
    from shop.models import TemplateFolder
    custom_folders = TemplateFolder.objects.all()
    for custom_folder in custom_folders:
        count = templates.filter(folder=custom_folder.name).count()
        folder_counts[custom_folder.name] = {'label': custom_folder.display_name, 'count': count, 'is_custom': True}

    # Build folder choices list including custom folders
    all_folder_choices = list(EmailTemplate.FOLDER_CHOICES)
    for custom_folder in custom_folders:
        all_folder_choices.append((custom_folder.name, custom_folder.display_name))

    context = {
        "templates": templates,
        "templates_json": templates_json,
        "edit_template": edit_template,
        "template_types": EmailTemplate.TEMPLATE_TYPES,
        "trigger_types": EmailTemplate.TRIGGER_TYPES,
        "folder_choices": all_folder_choices,
        "folder_counts": folder_counts,
        "custom_folders": custom_folders,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
        "total_count": total_count,
        "active_count": active_count,
        "inactive_count": inactive_count,
        "total_usage": total_usage,
        "all_tags": sorted(all_tags),
        "current_sort": sort_by,
    }

    return render(request, "admin/email_templates.html", context)


def messages_dashboard(request):
    """
    Dashboard showing all quick messages sent from the admin.
    """
    from shop.models.messaging import QuickMessage
    from shop.models.settings import SiteSettings

    # Handle image upload for email messages
    if request.method == "POST" and request.POST.get("action") == "upload_message_image":
        import base64
        import uuid
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        try:
            image_data = request.POST.get("image_data", "")
            if not image_data or "base64," not in image_data:
                return JsonResponse({"success": False, "error": "Invalid image data"})

            # Parse base64 data
            format_part, data_part = image_data.split("base64,", 1)
            image_content = base64.b64decode(data_part)

            if len(image_content) == 0:
                return JsonResponse({"success": False, "error": "Empty image"})

            if len(image_content) > 2 * 1024 * 1024:
                return JsonResponse({"success": False, "error": "Image too large (max 2MB)"})

            # Determine file extension from format
            ext = "jpg"
            if "png" in format_part.lower():
                ext = "png"
            elif "gif" in format_part.lower():
                ext = "gif"
            elif "webp" in format_part.lower():
                ext = "webp"

            # Save to media folder
            filename = f"messages/msg_{uuid.uuid4().hex[:8]}.{ext}"
            path = default_storage.save(filename, ContentFile(image_content))
            url = default_storage.url(path)

            return JsonResponse({"success": True, "url": url})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    # Handle POST request for saving test settings
    if request.method == "POST" and request.POST.get("action") == "save_test_settings":
        from django.http import JsonResponse

        try:
            settings = SiteSettings.load()
            settings.default_test_email = request.POST.get("test_email", "").strip()
            settings.default_test_phone = request.POST.get("test_phone", "").strip()
            settings.save()
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    # Handle cancel scheduled message
    if request.method == "POST" and request.POST.get("action") == "cancel_scheduled":
        from django.http import JsonResponse

        try:
            message_id = request.POST.get("message_id")
            message = QuickMessage.objects.get(id=message_id, status="scheduled")
            message.delete()
            return JsonResponse({"success": True})
        except QuickMessage.DoesNotExist:
            return JsonResponse({"success": False, "error": "Message not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    # Handle save draft
    if request.method == "POST" and request.POST.get("action") == "save_draft":
        from django.http import JsonResponse

        message_type = request.POST.get("message_type", "email")
        subject = request.POST.get("subject", "")
        content = request.POST.get("content", "")
        draft_id = request.POST.get("draft_id")
        scheduled_for_str = request.POST.get("scheduled_for", "").strip()

        # Parse scheduled_for if provided
        scheduled_for = None
        if scheduled_for_str:
            try:
                from datetime import datetime
                scheduled_for = datetime.fromisoformat(scheduled_for_str.replace("Z", "+00:00"))
                if timezone.is_naive(scheduled_for):
                    central_tz = pytz.timezone("America/Chicago")
                    scheduled_for = central_tz.localize(scheduled_for)
            except ValueError:
                pass

        try:
            if draft_id:
                # Update existing draft
                draft = QuickMessage.objects.get(id=draft_id, status="draft")
                draft.message_type = message_type
                draft.subject = subject
                draft.content = content
                draft.scheduled_for = scheduled_for
                draft.save()
            else:
                # Create new draft
                draft = QuickMessage.objects.create(
                    message_type=message_type,
                    subject=subject,
                    content=content,
                    status="draft",
                    scheduled_for=scheduled_for,
                )
            return JsonResponse({"success": True, "draft_id": draft.id})
        except QuickMessage.DoesNotExist:
            return JsonResponse({"success": False, "error": "Draft not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    # Get filter parameters
    message_type = request.GET.get("type", "all")
    date_range = request.GET.get("range", "30")

    # Base queryset - exclude drafts from main list
    messages = QuickMessage.objects.exclude(status="draft").order_by("-created_at")

    # Apply filters
    if message_type in ["email", "sms"]:
        messages = messages.filter(message_type=message_type)

    if date_range != "all":
        try:
            days = int(date_range)
            cutoff = timezone.now() - timedelta(days=days)
            messages = messages.filter(created_at__gte=cutoff)
        except ValueError:
            pass

    # Get drafts separately
    drafts = QuickMessage.objects.filter(status="draft").order_by("-updated_at")

    # Get scheduled messages separately
    scheduled_messages = QuickMessage.objects.filter(status="scheduled").order_by("scheduled_for")

    # Build timeline: combine scheduled messages + drafts with scheduled times + recently sent
    timeline_items = []

    # Add scheduled messages to timeline (pending)
    for msg in scheduled_messages:
        timeline_items.append({
            "id": msg.id,
            "type": "scheduled",
            "status": "pending",
            "message_type": msg.message_type,
            "subject": msg.subject,
            "content": msg.content,
            "scheduled_for": msg.scheduled_for,
            "sent_at": None,
            "recipient_count": msg.recipient_count,
            "sent_count": 0,
            "failed_count": 0,
        })

    # Add drafts with future scheduled times to timeline (skip past times)
    now = timezone.now()
    for draft in drafts.filter(scheduled_for__isnull=False, scheduled_for__gt=now):
        timeline_items.append({
            "id": draft.id,
            "type": "draft",
            "status": "draft",
            "message_type": draft.message_type,
            "subject": draft.subject,
            "content": draft.content,
            "scheduled_for": draft.scheduled_for,
            "sent_at": None,
            "recipient_count": 0,
            "sent_count": 0,
            "failed_count": 0,
        })

    # Sort by scheduled_for time
    timeline_items.sort(key=lambda x: x["scheduled_for"])

    # Calculate stats (exclude drafts and scheduled)
    sent_messages = QuickMessage.objects.exclude(status__in=["draft", "scheduled"])
    total_messages = sent_messages.count()
    total_sent = sent_messages.aggregate(total=Sum("sent_count"))["total"] or 0
    total_failed = sent_messages.aggregate(total=Sum("failed_count"))["total"] or 0
    email_messages = sent_messages.filter(message_type="email").count()
    sms_messages = sent_messages.filter(message_type="sms").count()
    draft_count = drafts.count()
    scheduled_count = scheduled_messages.count()

    # Get site settings for test defaults
    site_settings = SiteSettings.load()

    # Get subscriber counts for quick send form
    email_sub_count = EmailSubscription.objects.filter(is_active=True).count()
    sms_sub_count = SMSSubscription.objects.filter(is_active=True).count()

    context = {
        "messages": messages[:100],  # Limit to 100 most recent
        "drafts": drafts,
        "scheduled_messages": scheduled_messages,
        "timeline_items": timeline_items,
        "message_type": message_type,
        "date_range": date_range,
        "stats": {
            "total_messages": total_messages,
            "total_sent": total_sent,
            "total_failed": total_failed,
            "email_messages": email_messages,
            "sms_messages": sms_messages,
            "draft_count": draft_count,
            "scheduled_count": scheduled_count,
            "email_sub_count": email_sub_count,
            "sms_sub_count": sms_sub_count,
        },
        "default_test_email": site_settings.default_test_email,
        "default_test_phone": site_settings.default_test_phone,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/messages_dashboard.html", context)


def campaigns_list(request):
    """
    List all unified campaigns.
    """
    # Handle GET request for fetching message data
    if request.method == "GET" and request.GET.get("action") == "get_message":
        from django.http import JsonResponse

        try:
            message_id = request.GET.get("message_id")
            message = CampaignMessage.objects.get(id=message_id)

            return JsonResponse(
                {
                    "success": True,
                    "message": {
                        "id": message.id,
                        "message_type": message.message_type,
                        "custom_subject": message.custom_subject or "",
                        "custom_content": message.custom_content or "",
                        "media_urls": message.media_urls or "",
                        "notes": message.notes or "",
                        "send_mode": message.send_mode or "auto",
                    },
                }
            )
        except CampaignMessage.DoesNotExist:
            return JsonResponse({"success": False, "error": "Message not found"})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    if request.method == "POST":
        action = request.POST.get("action")
        campaign_id = request.POST.get("campaign_id")

        if action == "delete":
            try:
                campaign = Campaign.objects.get(id=campaign_id)
                campaign.delete()
                messages.success(request, "Campaign deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting campaign: {str(e)}")
            return redirect("admin_campaigns_list")

        elif action == "update_window":
            try:
                from django.http import JsonResponse

                campaign = Campaign.objects.get(id=campaign_id)

                active_from = request.POST.get("active_from")
                active_until = request.POST.get("active_until")

                campaign.active_from = active_from if active_from else None
                campaign.active_until = active_until if active_until else None
                campaign.save()

                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": True})
                else:
                    messages.success(request, "Operating window updated successfully!")
                    return redirect("admin_campaigns_list")
            except Exception as e:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": False, "error": str(e)})
                else:
                    messages.error(request, f"Error updating operating window: {str(e)}")
                    return redirect("admin_campaigns_list")

        elif action == "add_message":
            try:
                from datetime import datetime

                from django.db.models import Max

                campaign = Campaign.objects.get(id=campaign_id)
                message_type = request.POST.get("message_type")
                scheduled_date_str = request.POST.get("scheduled_date")

                # Get next order number
                max_order_result = campaign.messages.aggregate(max_order=Max("order"))
                max_order = (
                    max_order_result["max_order"]
                    if max_order_result["max_order"] is not None
                    else 0
                )
                next_order = max_order + 1

                # Parse scheduled date and time if provided
                scheduled_date = None
                if scheduled_date_str:
                    try:
                        # Parse date string (format: YYYY-MM-DD)
                        scheduled_date = timezone.datetime.strptime(scheduled_date_str, "%Y-%m-%d")

                        # Add time component if provided
                        scheduled_time_str = request.POST.get("scheduled_time")
                        if scheduled_time_str:
                            try:
                                time_parts = scheduled_time_str.split(":")
                                scheduled_date = scheduled_date.replace(
                                    hour=int(time_parts[0]),
                                    minute=int(time_parts[1]) if len(time_parts) > 1 else 0,
                                )
                            except (ValueError, IndexError):
                                pass

                        scheduled_date = timezone.make_aware(scheduled_date)
                    except ValueError:
                        pass

                # Get universal send_mode (fallback to type-specific if not provided)
                send_mode = request.POST.get("send_mode", "auto")

                # Create message based on type
                if message_type == "email":
                    subject = request.POST.get("email_subject", "").strip()
                    body = request.POST.get("email_body", "").strip()
                    recipient_group = request.POST.get("email_recipient", "all")
                    # Use type-specific send_mode if provided, otherwise use universal
                    send_mode = request.POST.get("email_send_mode", send_mode)

                    if not subject or not body:
                        messages.error(request, "Email subject and body are required!")
                        return redirect("admin_campaigns_list")

                    # Map recipient group to display name
                    recipient_display = {
                        "all": "All Email Subscribers",
                        "new_customers": "New Customers (Last 30 days)",
                        "vip": "VIP Customers",
                        "inactive": "Inactive Customers",
                        "custom": "Custom Selection",
                    }.get(recipient_group, "All Email Subscribers")

                    # Set status based on send mode
                    msg_status = "draft" if send_mode == "draft" else "pending"

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="email",
                        name=f"{subject} → {recipient_display}",
                        custom_subject=subject,
                        custom_content=body,
                        order=next_order,
                        status=msg_status,
                        send_mode=send_mode,
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    messages.success(
                        request,
                        f'Email message "{subject}" added to campaign for {recipient_display}!',
                    )

                elif message_type == "sms":
                    sms_message = request.POST.get("sms_message", "").strip()
                    recipient_group = request.POST.get("sms_to", "all")
                    # Use type-specific send_mode if provided, otherwise use universal
                    send_mode = request.POST.get("sms_send_mode", send_mode)

                    if not sms_message:
                        messages.error(request, "SMS message is required!")
                        return redirect("admin_campaigns_list")

                    # Map recipient group to display name
                    recipient_display = {
                        "all": "All SMS Subscribers",
                        "new_customers": "New Customers (Last 30 days)",
                        "vip": "VIP Customers",
                        "inactive": "Inactive Customers",
                        "custom": "Custom Selection",
                    }.get(recipient_group, "All SMS Subscribers")

                    # Set status based on send mode
                    msg_status = "draft" if send_mode == "draft" else "pending"

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="sms",
                        name=(
                            f"{sms_message[:30]}... → {recipient_display}"
                            if len(sms_message) > 30
                            else f"{sms_message} → {recipient_display}"
                        ),
                        custom_content=sms_message,
                        order=next_order,
                        status=msg_status,
                        send_mode=send_mode,
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    messages.success(
                        request, f"SMS message added to campaign for {recipient_display}!"
                    )

                elif message_type == "instagram":
                    caption = request.POST.get("instagram_caption", "").strip()
                    media_urls = request.POST.get("instagram_media", "").strip()
                    notes = request.POST.get("instagram_notes", "").strip()

                    # Set status based on send mode
                    msg_status = "draft" if send_mode == "draft" else "pending"

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="instagram",
                        name=(
                            f"Instagram: {caption[:40]}..."
                            if len(caption) > 40
                            else f"Instagram: {caption}" if caption else "Instagram Post"
                        ),
                        custom_subject=caption,  # Caption
                        custom_content=notes,  # Notes
                        media_urls=media_urls,
                        notes=notes,
                        order=next_order,
                        status=msg_status,
                        send_mode=send_mode,
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    messages.success(request, "Instagram post added to campaign!")

                elif message_type == "tiktok":
                    caption = request.POST.get("tiktok_caption", "").strip()
                    media_url = request.POST.get("tiktok_media", "").strip()
                    notes = request.POST.get("tiktok_notes", "").strip()

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="tiktok",
                        name=(
                            f"TikTok: {caption[:40]}..."
                            if len(caption) > 40
                            else f"TikTok: {caption}" if caption else "TikTok Video"
                        ),
                        custom_subject=caption,
                        custom_content=notes,
                        media_urls=media_url,
                        notes=notes,
                        order=next_order,
                        status="draft",
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    messages.success(request, "TikTok video added to campaign!")

                elif message_type == "snapchat":
                    caption = request.POST.get("snapchat_caption", "").strip()
                    media_url = request.POST.get("snapchat_media", "").strip()
                    notes = request.POST.get("snapchat_notes", "").strip()

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="snapchat",
                        name=(
                            f"Snapchat: {caption[:40]}..."
                            if len(caption) > 40
                            else f"Snapchat: {caption}" if caption else "Snapchat Story"
                        ),
                        custom_subject=caption,
                        custom_content=notes,
                        media_urls=media_url,
                        notes=notes,
                        order=next_order,
                        status="draft",
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    messages.success(request, "Snapchat story added to campaign!")

                elif message_type == "youtube":
                    title = request.POST.get("youtube_title", "").strip()
                    video_url = request.POST.get("youtube_url", "").strip()
                    description = request.POST.get("youtube_description", "").strip()

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="youtube",
                        name=(
                            f"YouTube: {title[:40]}..."
                            if len(title) > 40
                            else f"YouTube: {title}" if title else "YouTube Video"
                        ),
                        custom_subject=title,
                        custom_content=description,
                        media_urls=video_url,
                        notes=description,
                        order=next_order,
                        status="draft",
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    messages.success(request, "YouTube video added to campaign!")

                elif message_type == "promotion":
                    from decimal import Decimal

                    from shop.models import Discount, Product

                    promo_title = request.POST.get("promotion_title", "").strip()
                    promo_type = request.POST.get("promotion_type", "public").strip()
                    promo_code = request.POST.get("promotion_code", "").strip().upper()
                    discount_type = request.POST.get(
                        "promotion_discount_type", "percentage"
                    ).strip()
                    discount_value = request.POST.get("promotion_discount_value", "").strip()
                    product_ids = request.POST.getlist("promotion_products")
                    promo_details = request.POST.get("promotion_details", "").strip()

                    if not promo_title:
                        messages.error(request, "Promotion title is required!")
                        return redirect("admin_campaigns_list")

                    # Validate discount amount for all promotions (except BOGO and Free Shipping)
                    if discount_type not in ["bogo", "free_shipping"] and not discount_value:
                        messages.error(request, "Discount amount is required!")
                        return redirect("admin_campaigns_list")

                    # Validate private promotion requirements
                    if promo_type == "private":
                        if not promo_code:
                            messages.error(
                                request, "Discount code is required for private promotions!"
                            )
                            return redirect("admin_campaigns_list")

                        # Check code uniqueness
                        if Discount.objects.filter(code=promo_code).exists():
                            messages.error(
                                request,
                                f'Discount code "{promo_code}" already exists! Please use a different code.',
                            )
                            return redirect("admin_campaigns_list")

                    # Build notes with promotion type and code info
                    notes_parts = []
                    if promo_type == "public":
                        notes_parts.append("Type: Public Sale (No code required)")
                    else:
                        notes_parts.append("Type: Private/Code Only")
                        if promo_code:
                            notes_parts.append(f"Code: {promo_code}")

                    if promo_details:
                        notes_parts.append(f"\nDetails: {promo_details}")

                    combined_notes = "\n".join(notes_parts)

                    # Create the message
                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="promotion",
                        name=(
                            f"Promo: {promo_title[:40]}..."
                            if len(promo_title) > 40
                            else f"Promo: {promo_title}"
                        ),
                        custom_subject=promo_title,
                        custom_content=promo_details,
                        notes=combined_notes,
                        order=next_order,
                        status="draft",
                        trigger_type="specific_date" if scheduled_date else "immediate",
                        scheduled_date=scheduled_date,
                    )

                    # Create discount for all promotions
                    try:
                        # For BOGO, use 50 as the value (50% off second item is standard)
                        # For Free Shipping, use 0 (just a flag, actual shipping cost calculated at checkout)
                        if discount_type == "bogo":
                            discount_value = "50"
                        elif discount_type == "free_shipping":
                            discount_value = "0"

                        if discount_value:
                            # Generate a code for public promotions if not provided
                            if not promo_code:
                                # Auto-generate code for public sales (e.g., PUBLIC_SALE_12345)
                                import random

                                promo_code = f"AUTO_{random.randint(10000, 99999)}"

                            discount = Discount.objects.create(
                                name=promo_title,
                                code=promo_code,
                                discount_type=discount_type,
                                value=Decimal(discount_value),
                                valid_from=timezone.now(),
                                is_active=True,
                                applies_to_all=False if product_ids else True,
                            )
                            # Link products to discount if specified
                            if product_ids:
                                products_for_discount = Product.objects.filter(id__in=product_ids)
                                discount.products.set(products_for_discount)

                            message.discount = discount
                            message.save()
                    except Exception as e:
                        messages.error(request, f"Error creating discount: {str(e)}")
                        return redirect("admin_campaigns_list")

                    # Link products to message if selected
                    if product_ids:
                        products = Product.objects.filter(id__in=product_ids)
                        message.products.set(products)

                    success_msg = f"{'Public sale' if promo_type == 'public' else 'Private promotion'} added to campaign!"
                    if promo_code:
                        success_msg += f" Code: {promo_code}"
                    messages.success(request, success_msg)

                elif message_type == "product":
                    from shop.models import Product, ProductVariant

                    product_variant = request.POST.get("product_variant", "").strip()
                    announcement_title = request.POST.get("product_announcement_title", "").strip()
                    announcement_details = request.POST.get(
                        "product_announcement_details", ""
                    ).strip()
                    media_url = request.POST.get("product_media_url", "").strip()
                    release_time = request.POST.get("product_release_time", "09:00").strip()

                    if not product_variant:
                        messages.error(request, "Product or variant selection is required!")
                        return redirect("admin_campaigns_list")

                    # Parse product_variant (format: "product_123" or "variant_456")
                    product_name = ""
                    selected_products = []
                    if product_variant.startswith("product_"):
                        product_id = product_variant.replace("product_", "")
                        try:
                            product = Product.objects.get(id=product_id)
                            product_name = f"{product.name} (All Variants)"
                            selected_products = [product]
                        except Product.DoesNotExist:
                            messages.error(request, "Selected product not found!")
                            return redirect("admin_campaigns_list")
                    elif product_variant.startswith("variant_"):
                        variant_id = product_variant.replace("variant_", "")
                        try:
                            variant = ProductVariant.objects.get(id=variant_id)
                            product_name = f"{variant.product.name} - {variant.name}"
                            selected_products = [variant.product]
                        except ProductVariant.DoesNotExist:
                            messages.error(request, "Selected variant not found!")
                            return redirect("admin_campaigns_list")

                    # Build message name and notes
                    name = (
                        announcement_title
                        if announcement_title
                        else f"Product Release: {product_name}"
                    )
                    notes = f"Product: {product_name}\nRelease Time: {release_time}"
                    if announcement_details:
                        notes += f"\nDetails: {announcement_details}"

                    # Combine scheduled date with release time if provided
                    product_scheduled_date = scheduled_date
                    if scheduled_date and release_time:
                        try:
                            time_parts = release_time.split(":")
                            product_scheduled_date = scheduled_date.replace(
                                hour=int(time_parts[0]),
                                minute=int(time_parts[1]) if len(time_parts) > 1 else 0,
                            )
                        except (ValueError, IndexError):
                            pass

                    message = CampaignMessage.objects.create(
                        campaign=campaign,
                        message_type="product",
                        name=name,
                        custom_subject=announcement_title,
                        custom_content=announcement_details,
                        media_urls=media_url,
                        notes=notes,
                        order=next_order,
                        status="draft",
                        trigger_type="specific_date" if product_scheduled_date else "immediate",
                        scheduled_date=product_scheduled_date,
                    )

                    # Link products to message
                    if selected_products:
                        message.products.set(selected_products)

                    messages.success(request, f'Product release "{name}" added to campaign!')

                return redirect("admin_campaigns_list")
            except Campaign.DoesNotExist:
                messages.error(request, "Campaign not found!")
                return redirect("admin_campaigns_list")
            except Exception as e:
                messages.error(request, f"Error adding message: {str(e)}")
                return redirect("admin_campaigns_list")

        elif action == "update_message_date":
            try:
                from django.http import JsonResponse

                message_id = request.POST.get("message_id")
                scheduled_date_str = request.POST.get("scheduled_date")

                message = CampaignMessage.objects.get(id=message_id)

                # Parse scheduled date
                if scheduled_date_str:
                    try:
                        # Parse date string (format: YYYY-MM-DD)
                        scheduled_date = timezone.datetime.strptime(scheduled_date_str, "%Y-%m-%d")
                        scheduled_date = timezone.make_aware(scheduled_date)
                        message.scheduled_date = scheduled_date
                        message.trigger_type = "specific_date"
                        message.save()

                        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                            return JsonResponse({"success": True})
                        else:
                            messages.success(request, "Message date updated successfully!")
                            return redirect("admin_campaigns_list")
                    except ValueError as e:
                        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                            return JsonResponse(
                                {"success": False, "error": f"Invalid date format: {str(e)}"}
                            )
                        else:
                            messages.error(request, f"Invalid date format: {str(e)}")
                            return redirect("admin_campaigns_list")
                else:
                    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                        return JsonResponse({"success": False, "error": "No date provided"})
                    else:
                        messages.error(request, "No date provided")
                        return redirect("admin_campaigns_list")
            except CampaignMessage.DoesNotExist:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": False, "error": "Message not found"})
                else:
                    messages.error(request, "Message not found!")
                    return redirect("admin_campaigns_list")
            except Exception as e:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": False, "error": str(e)})
                else:
                    messages.error(request, f"Error updating message date: {str(e)}")
                    return redirect("admin_campaigns_list")

        elif action == "edit_message":
            try:
                from django.http import JsonResponse

                message_id = request.POST.get("message_id")
                message = CampaignMessage.objects.get(id=message_id)
                message_type = message.message_type

                # Update based on message type
                if message_type == "email":
                    message.custom_subject = request.POST.get("email_subject", "").strip()
                    message.custom_content = request.POST.get("email_body", "").strip()
                    message.send_mode = request.POST.get("email_send_mode", "auto")
                    message.status = "draft" if message.send_mode == "draft" else message.status
                elif message_type == "sms":
                    message.custom_content = request.POST.get("sms_message", "").strip()
                    message.send_mode = request.POST.get("sms_send_mode", "auto")
                    message.status = "draft" if message.send_mode == "draft" else message.status
                elif message_type == "instagram":
                    message.custom_subject = request.POST.get("instagram_caption", "").strip()
                    message.media_urls = request.POST.get("instagram_media", "").strip()
                    message.notes = request.POST.get("instagram_notes", "").strip()
                    message.custom_content = message.notes
                elif message_type == "tiktok":
                    message.custom_subject = request.POST.get("tiktok_caption", "").strip()
                    message.media_urls = request.POST.get("tiktok_media", "").strip()
                    message.notes = request.POST.get("tiktok_notes", "").strip()
                    message.custom_content = message.notes
                elif message_type == "snapchat":
                    message.custom_subject = request.POST.get("snapchat_caption", "").strip()
                    message.media_urls = request.POST.get("snapchat_media", "").strip()
                    message.notes = request.POST.get("snapchat_notes", "").strip()
                    message.custom_content = message.notes
                elif message_type == "youtube":
                    message.custom_subject = request.POST.get("youtube_title", "").strip()
                    message.media_urls = request.POST.get("youtube_url", "").strip()
                    message.notes = request.POST.get("youtube_description", "").strip()
                    message.custom_content = message.notes
                elif message_type == "promotion":
                    from shop.models import Discount, Product

                    promo_title = request.POST.get("promotion_title", "").strip()
                    promo_type = request.POST.get("promotion_type", "public").strip()
                    promo_code = request.POST.get("promotion_code", "").strip()
                    promo_details = request.POST.get("promotion_details", "").strip()

                    message.custom_subject = promo_title
                    message.custom_content = promo_details

                    # Build notes with promotion type and code info
                    notes_parts = []
                    if promo_type == "public":
                        notes_parts.append("Type: Public Sale (No code required)")
                    else:
                        notes_parts.append("Type: Private/Code Only")
                        if promo_code:
                            notes_parts.append(f"Code: {promo_code}")

                    if promo_details:
                        notes_parts.append(f"\nDetails: {promo_details}")

                    message.notes = "\n".join(notes_parts)

                    # Update discount if changed
                    discount_id = request.POST.get("promotion_discount", "").strip()
                    if discount_id:
                        try:
                            discount = Discount.objects.get(id=discount_id)
                            message.discount = discount
                        except Discount.DoesNotExist:
                            message.discount = None
                    else:
                        message.discount = None

                    # Update products if changed
                    product_ids = request.POST.getlist("promotion_products")
                    if product_ids:
                        products = Product.objects.filter(id__in=product_ids)
                        message.products.set(products)
                    else:
                        message.products.clear()

                message.save()

                messages.success(request, "Message updated successfully!")
                return redirect("admin_campaigns_list")
            except CampaignMessage.DoesNotExist:
                messages.error(request, "Message not found!")
                return redirect("admin_campaigns_list")
            except Exception as e:
                messages.error(request, f"Error updating message: {str(e)}")
                return redirect("admin_campaigns_list")

        elif action == "delete_message":
            try:
                from django.http import JsonResponse

                message_id = request.POST.get("message_id")
                message = CampaignMessage.objects.get(id=message_id)
                message.delete()

                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": True})
                else:
                    messages.success(request, "Message deleted successfully!")
                    return redirect("admin_campaigns_list")
            except CampaignMessage.DoesNotExist:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": False, "error": "Message not found"})
                else:
                    messages.error(request, "Message not found!")
                    return redirect("admin_campaigns_list")
            except Exception as e:
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"success": False, "error": str(e)})
                else:
                    messages.error(request, f"Error deleting message: {str(e)}")
                    return redirect("admin_campaigns_list")

        elif action == "change_message_status":
            try:
                from django.http import JsonResponse

                message_id = request.POST.get("message_id")
                new_status = request.POST.get("status")

                message = CampaignMessage.objects.get(id=message_id)
                message.status = new_status

                # Update sent_at if status is changed to 'sent'
                if new_status == "sent" and not message.sent_at:
                    message.sent_at = timezone.now()

                message.save()

                return JsonResponse({"success": True})
            except CampaignMessage.DoesNotExist:
                return JsonResponse({"success": False, "error": "Message not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

        elif action == "change_campaign_status":
            try:
                from django.http import JsonResponse

                campaign_id = request.POST.get("campaign_id")
                new_status = request.POST.get("status")

                campaign = Campaign.objects.get(id=campaign_id)
                campaign.status = new_status

                # Update started_at if status is changed to 'active' and not set
                if new_status == "active" and not campaign.started_at:
                    campaign.started_at = timezone.now()

                # Update completed_at if status is changed to 'completed'
                if new_status == "completed" and not campaign.completed_at:
                    campaign.completed_at = timezone.now()

                campaign.save()

                return JsonResponse({"success": True})
            except Campaign.DoesNotExist:
                return JsonResponse({"success": False, "error": "Campaign not found"})
            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

    from django.db.models import Count, Q

    campaigns_queryset = Campaign.objects.all().prefetch_related("messages").order_by("-created_at")
    now = timezone.now()

    # Build enriched campaign data
    campaigns = []
    for campaign in campaigns_queryset:
        # Get message counts
        total_messages = campaign.messages.count()
        sent_messages = campaign.messages.filter(status="sent").count()

        # Get message sequence ordered by order field
        message_sequence = list(
            campaign.messages.all()
            .order_by("order")
            .values("id", "message_type", "status", "name", "scheduled_date", "sent_at")
        )

        # Count messages by type
        email_count = sum(1 for m in message_sequence if m["message_type"] == "email")
        sms_count = sum(1 for m in message_sequence if m["message_type"] == "sms")
        instagram_count = sum(1 for m in message_sequence if m["message_type"] == "instagram")
        tiktok_count = sum(1 for m in message_sequence if m["message_type"] == "tiktok")
        snapchat_count = sum(1 for m in message_sequence if m["message_type"] == "snapchat")

        # Calculate progress percentage
        if total_messages > 0:
            progress_percentage = int((sent_messages / total_messages) * 100)
        else:
            progress_percentage = 0

        # Determine display status
        if campaign.active_from and campaign.active_until:
            if now < campaign.active_from:
                display_status = "upcoming"
            elif now > campaign.active_until:
                display_status = "completed"
            else:
                display_status = "active"
        elif campaign.active_from:
            if now >= campaign.active_from:
                display_status = "active"
            else:
                display_status = "upcoming"
        elif campaign.active_until:
            if now <= campaign.active_until:
                display_status = "active"
            else:
                display_status = "completed"
        else:
            display_status = "draft"

        # Create enriched campaign object
        campaign_data = {
            "id": campaign.id,
            "name": campaign.name,
            "description": campaign.description,
            "target_group": campaign.target_group,
            "active_from": campaign.active_from,
            "active_until": campaign.active_until,
            "created_at": campaign.created_at,
            "total_messages": total_messages,
            "sent_messages": sent_messages,
            "progress_percentage": progress_percentage,
            "display_status": display_status,
            "message_sequence": message_sequence,
            "email_count": email_count,
            "sms_count": sms_count,
            "instagram_count": instagram_count,
            "tiktok_count": tiktok_count,
            "snapchat_count": snapchat_count,
        }
        campaigns.append(campaign_data)

    # Calculate overview stats
    total_campaigns = len(campaigns)
    active_campaigns = sum(1 for c in campaigns if c["display_status"] == "active")
    upcoming_campaigns = sum(1 for c in campaigns if c["display_status"] == "upcoming")
    total_messages = sum(c["total_messages"] for c in campaigns)
    sent_messages = sum(c["sent_messages"] for c in campaigns)

    # Get timeline campaigns (upcoming and active, sorted by start date)
    timeline_campaigns = [c for c in campaigns if c["display_status"] in ["upcoming", "active"]]
    timeline_campaigns.sort(key=lambda c: c["active_from"] if c["active_from"] else timezone.now())

    # Get upcoming messages (not sent yet, across all campaigns)
    upcoming_messages = (
        CampaignMessage.objects.select_related("campaign")
        .exclude(status="sent")
        .order_by("scheduled_date", "created_at")[:20]
    )
    upcoming_messages_data = []
    for msg in upcoming_messages:
        upcoming_messages_data.append(
            {
                "id": msg.id,
                "name": msg.name,
                "message_type": msg.message_type,
                "campaign_name": msg.campaign.name,
                "campaign_id": msg.campaign.id,
                "status": msg.status,
                "scheduled_date": msg.scheduled_date,
                "created_at": msg.created_at,
                "custom_subject": msg.custom_subject,
            }
        )

    # Get recent messages across all campaigns (most recent 20 sent messages)
    recent_messages = (
        CampaignMessage.objects.select_related("campaign")
        .filter(status="sent")
        .order_by("-sent_at")[:20]
    )
    recent_messages_data = []
    for msg in recent_messages:
        recent_messages_data.append(
            {
                "id": msg.id,
                "name": msg.name,
                "message_type": msg.message_type,
                "campaign_name": msg.campaign.name,
                "campaign_id": msg.campaign.id,
                "status": msg.status,
                "scheduled_date": msg.scheduled_date,
                "sent_at": msg.sent_at,
                "created_at": msg.created_at,
                "custom_subject": msg.custom_subject,
            }
        )

    # Get products for promotion message form
    from shop.models import Product

    products = Product.objects.filter(is_active=True).order_by("name")

    context = {
        "campaigns": campaigns,
        "timeline_campaigns": timeline_campaigns,
        "upcoming_messages": upcoming_messages_data,
        "recent_messages": recent_messages_data,
        "total_campaigns": total_campaigns,
        "active_campaigns": active_campaigns,
        "upcoming_campaigns": upcoming_campaigns,
        "total_messages": total_messages,
        "sent_messages": sent_messages,
        "products": products,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/campaigns_list.html", context)


def all_campaigns(request):
    """
    Unified view showing both email and SMS campaigns together.
    """
    from shop.models import EmailCampaign, SMSCampaign

    # Get all email campaigns
    email_campaigns = EmailCampaign.objects.all().select_related("template")
    email_list = []
    for campaign in email_campaigns:
        email_list.append(
            {
                "id": campaign.id,
                "type": "email",
                "name": campaign.name,
                "template": campaign.template,
                "status": campaign.status,
                "get_status_display": campaign.get_status_display(),
                "scheduled_at": campaign.scheduled_at,
                "total_recipients": campaign.total_recipients,
                "sent_count": campaign.sent_count,
                "created_at": campaign.created_at,
            }
        )

    # Get all SMS campaigns
    sms_campaigns = SMSCampaign.objects.all().select_related("template")
    sms_list = []
    for campaign in sms_campaigns:
        sms_list.append(
            {
                "id": campaign.id,
                "type": "sms",
                "name": campaign.name,
                "template": campaign.template,
                "status": campaign.status,
                "get_status_display": campaign.get_status_display(),
                "scheduled_at": campaign.scheduled_at,
                "total_recipients": campaign.total_recipients,
                "sent_count": campaign.sent_count,
                "created_at": campaign.created_at,
            }
        )

    # Combine and sort by created_at
    all_campaigns_list = email_list + sms_list
    all_campaigns_list.sort(key=lambda x: x["created_at"], reverse=True)

    context = {
        "campaigns": all_campaigns_list,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/all_campaigns.html", context)


@staff_member_required
def campaign_create(request):
    """
    Create and manage unified campaigns containing multiple scheduled email/SMS messages.
    Example: "Fall Sale 2025" campaign with welcome email, follow-up SMS, reminder email.
    """
    if request.method == "POST":
        action = request.POST.get("action")

        if action == "create_campaign":
            name = request.POST.get("name")
            description = request.POST.get("description", "")
            target_group = request.POST.get("target_group", "")
            active_from = request.POST.get("active_from")
            active_until = request.POST.get("active_until")

            try:
                campaign = Campaign.objects.create(
                    name=name,
                    description=description,
                    target_group=target_group,
                    active_from=active_from if active_from else None,
                    active_until=active_until if active_until else None,
                    created_by=request.user,
                )
                messages.success(request, f'Campaign "{campaign.name}" created successfully!')
                return redirect("admin_campaign_edit", campaign_id=campaign.id)
            except Exception as e:
                messages.error(request, f"Error creating campaign: {str(e)}")

    # Get all email and SMS templates
    email_templates = EmailTemplate.objects.filter(is_active=True).order_by("name")
    sms_templates = SMSTemplate.objects.filter(is_active=True).order_by("name")

    context = {
        "email_templates": email_templates,
        "sms_templates": sms_templates,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/campaign_create.html", context)


@staff_member_required
def campaign_edit(request, campaign_id):
    """
    Edit campaign and manage its messages.
    """
    try:
        campaign = Campaign.objects.get(id=campaign_id)
    except Campaign.DoesNotExist:
        messages.error(request, "Campaign not found")
        return redirect("admin_campaigns_list")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_campaign":
            campaign.name = request.POST.get("name")
            campaign.description = request.POST.get("description", "")
            campaign.target_group = request.POST.get("target_group", "")

            active_from = request.POST.get("active_from")
            active_until = request.POST.get("active_until")
            campaign.active_from = active_from if active_from else None
            campaign.active_until = active_until if active_until else None

            campaign.save()
            messages.success(request, f'Campaign "{campaign.name}" updated successfully!')
            return redirect("admin_campaign_edit", campaign_id=campaign.id)

        elif action == "add_message":
            name = request.POST.get("message_name")
            message_type = request.POST.get("message_type")
            trigger_type = request.POST.get("trigger_type")
            order = request.POST.get("order", 0)
            custom_subject = request.POST.get("custom_subject", "")
            custom_content = request.POST.get("custom_content", "")

            # Get template if specified
            email_template_id = request.POST.get("email_template")
            sms_template_id = request.POST.get("sms_template")

            try:
                message = CampaignMessage.objects.create(
                    campaign=campaign,
                    name=name,
                    message_type=message_type,
                    trigger_type=trigger_type,
                    order=int(order),
                    custom_subject=custom_subject,
                    custom_content=custom_content,
                )

                if message_type == "email" and email_template_id:
                    message.email_template = EmailTemplate.objects.get(id=email_template_id)
                elif message_type == "sms" and sms_template_id:
                    message.sms_template = SMSTemplate.objects.get(id=sms_template_id)

                # Handle delay settings
                if trigger_type == "delay":
                    message.delay_days = int(request.POST.get("delay_days", 0))
                    message.delay_hours = int(request.POST.get("delay_hours", 0))
                elif trigger_type == "specific_date":
                    scheduled_date = request.POST.get("scheduled_date")
                    if scheduled_date:
                        message.scheduled_date = scheduled_date

                message.save()
                messages.success(request, f'Message "{message.name}" added successfully!')
                return redirect("admin_campaign_edit", campaign_id=campaign.id)
            except Exception as e:
                messages.error(request, f"Error adding message: {str(e)}")

        elif action == "delete_message":
            message_id = request.POST.get("message_id")
            try:
                message = CampaignMessage.objects.get(id=message_id, campaign=campaign)
                message.delete()
                messages.success(request, "Message deleted successfully!")
            except Exception as e:
                messages.error(request, f"Error deleting message: {str(e)}")
            return redirect("admin_campaign_edit", campaign_id=campaign.id)

    # Get campaign messages ordered by sequence
    messages_list = campaign.messages.all().order_by("order", "created_at")

    # Get templates
    email_templates = EmailTemplate.objects.filter(is_active=True).order_by("name")
    sms_templates = SMSTemplate.objects.filter(is_active=True).order_by("name")

    context = {
        "campaign": campaign,
        "messages_list": messages_list,
        "email_templates": email_templates,
        "sms_templates": sms_templates,
        "cst_time": timezone.now().astimezone(pytz.timezone("America/Chicago")),
    }

    return render(request, "admin/campaign_edit.html", context)


