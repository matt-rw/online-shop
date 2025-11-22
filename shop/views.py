import logging

from django.contrib import messages
from django.core.mail import send_mail
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django_ratelimit.decorators import ratelimit

from .forms import SubscribeForm
from .models import EmailSubscription
from .utils.validators import validate_and_format_phone_number

logger = logging.getLogger(__name__)


@ratelimit(key="ip", rate="10/h", method="POST")
def subscribe(request):
    if request.method == "POST":
        form = SubscribeForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data

            try:
                # Populate if email is new
                sub, created = EmailSubscription.objects.get_or_create(email=data["email"])

                if created:
                    logger.info(f"New email subscription: {sub.email}")
                    messages.success(request, "Thank you for subscribing!")
                else:
                    logger.info(f"Existing subscription attempt: {sub.email}")
                    messages.info(request, "You're already subscribed!")

                # TODO: Send confirmation email when ready
                # full_message = f"Thank you for subscribing to Blueprint Apparel!"
                # send_mail(
                #     subject='Welcome to Blueprint Apparel',
                #     message=full_message,
                #     from_email=settings.DEFAULT_FROM_EMAIL,
                #     recipient_list=[sub.email],
                #     fail_silently=False
                # )

                return redirect("/#subscribe")

            except Exception as e:
                logger.error(f"Error creating subscription: {e}")
                messages.error(request, "Something went wrong. Please try again.")
                return redirect("/#subscribe")

        else:
            logger.warning(f"Invalid subscription form submission: {form.errors}")
            messages.error(request, "Please enter a valid email address.")
            return redirect("/#subscribe")

    # GET request
    form = SubscribeForm()
    return render(request, "home/home_page.html", {"form": form})


@ratelimit(key="ip", rate="5/h", method="POST")
def subscribe_sms(request):
    """Handle SMS subscription sign-ups"""
    if request.method == "POST":
        phone_number = request.POST.get("phone_number", "").strip()

        if not phone_number:
            messages.error(request, "Please enter a phone number.")
            return redirect("/#subscribe")

        # Validate and format phone number using phonenumbers library
        is_valid, formatted_number, error_message = validate_and_format_phone_number(phone_number)

        if not is_valid:
            messages.error(request, f"Invalid phone number: {error_message}")
            logger.warning(f"Invalid phone number submission: {phone_number}")
            return redirect("/#subscribe")

        phone_number = formatted_number

        try:
            from shop.models import SMSSubscription
            from shop.utils.twilio_helper import trigger_auto_send

            # Create or get subscription
            subscription, created = SMSSubscription.objects.get_or_create(
                phone_number=phone_number, defaults={"source": "site_form"}
            )

            if created:
                logger.info(f"New SMS subscription: {subscription.phone_number}")

                # Trigger automatic welcome message if configured
                trigger_auto_send("on_subscribe", subscription)

                messages.success(request, "Thank you for subscribing to SMS updates!")
            else:
                if subscription.is_active:
                    logger.info(f"Existing SMS subscription attempt: {subscription.phone_number}")
                    messages.info(request, "You're already subscribed to SMS updates!")
                else:
                    # Reactivate subscription
                    subscription.is_active = True
                    subscription.unsubscribed_at = None
                    subscription.save()
                    logger.info(f"Reactivated SMS subscription: {subscription.phone_number}")
                    messages.success(
                        request, "Welcome back! You're now resubscribed to SMS updates."
                    )

            return redirect("/#subscribe")

        except Exception as e:
            logger.error(f"Error creating SMS subscription: {e}")
            messages.error(request, "Something went wrong. Please try again.")
            return redirect("/#subscribe")

    return redirect("/#subscribe")


# ============================================
# HEALTH CHECK ENDPOINTS
# ============================================


def health_check(request):
    """
    Basic health check endpoint for monitoring.
    Returns 200 OK if application is running.
    URL: /shop/health/
    """
    from django.http import JsonResponse

    return JsonResponse({"status": "healthy", "service": "blueprint-apparel"})


def health_check_detailed(request):
    """
    Detailed health check with database and cache status.
    URL: /shop/health/detailed/
    """
    import time

    from django.conf import settings
    from django.core.cache import cache
    from django.db import connection
    from django.http import JsonResponse

    start_time = time.time()
    checks = {}
    all_healthy = True

    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = {"status": "healthy"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        all_healthy = False

    # Cache check
    try:
        cache.set("health_check", "ok", 10)
        if cache.get("health_check") == "ok":
            checks["cache"] = {"status": "healthy"}
        else:
            checks["cache"] = {"status": "degraded"}
    except Exception as e:
        checks["cache"] = {"status": "unhealthy", "error": str(e)}
        all_healthy = False

    response_time_ms = (time.time() - start_time) * 1000

    response_data = {
        "status": "healthy" if all_healthy else "unhealthy",
        "response_time_ms": round(response_time_ms, 2),
        "checks": checks,
        "service": "blueprint-apparel",
    }

    return JsonResponse(response_data, status=200 if all_healthy else 503)


# TODO: Implement email confirmation flow
# def confirm_subscription(request):
#     email = request.GET.get('email')
#     token = request.GET.get('token')
#     try:
#         sub = EmailSubscription.objects.get(email=email, unsub_token=token)
#         sub.is_confirmed = True
#         sub.save()
#         messages.success(request, "Email confirmed! Thank you for subscribing.")
#     except EmailSubscription.DoesNotExist:
#         messages.error(request, "Invalid confirmation link.")
#     return redirect('home:home')


@csrf_exempt
@require_http_methods(["GET", "POST"])
def process_campaigns_webhook(request):
    """
    Webhook endpoint to process scheduled campaigns.
    Call this from external cron services (cron-job.org, etc.)

    Security: Requires CAMPAIGN_WEBHOOK_SECRET in environment

    Usage:
        GET/POST https://yourdomain.com/campaigns/process/?secret=YOUR_SECRET
    """
    from django.conf import settings
    from django.utils import timezone

    # Check secret key for security
    secret = request.GET.get('secret') or request.POST.get('secret')
    expected_secret = getattr(settings, 'CAMPAIGN_WEBHOOK_SECRET', None)

    if not expected_secret:
        logger.error("CAMPAIGN_WEBHOOK_SECRET not configured in settings")
        return JsonResponse({
            'error': 'Webhook not configured',
            'status': 'error'
        }, status=500)

    if secret != expected_secret:
        logger.warning(f"Invalid webhook secret attempted from {request.META.get('REMOTE_ADDR')}")
        return JsonResponse({
            'error': 'Invalid secret',
            'status': 'unauthorized'
        }, status=401)

    # Process email campaigns
    from .models import EmailCampaign, SMSCampaign
    from .utils.email_helper import send_campaign as send_email_campaign
    from .utils.twilio_helper import send_campaign as send_sms_campaign

    results = {
        'timestamp': timezone.now().isoformat(),
        'email_campaigns': {'processed': 0, 'sent': 0, 'failed': 0, 'errors': []},
        'sms_campaigns': {'processed': 0, 'sent': 0, 'failed': 0, 'errors': []},
    }

    now = timezone.now()

    # Process email campaigns
    try:
        email_campaigns = EmailCampaign.objects.filter(
            status='scheduled',
            scheduled_at__lte=now
        )

        for campaign in email_campaigns:
            results['email_campaigns']['processed'] += 1
            try:
                result = send_email_campaign(campaign)
                if 'error' in result:
                    results['email_campaigns']['failed'] += 1
                    results['email_campaigns']['errors'].append({
                        'campaign_id': campaign.id,
                        'name': campaign.name,
                        'error': result['error']
                    })
                else:
                    results['email_campaigns']['sent'] += result.get('sent', 0)
                    results['email_campaigns']['failed'] += result.get('failed', 0)
            except Exception as e:
                logger.error(f"Error processing email campaign {campaign.id}: {str(e)}")
                results['email_campaigns']['errors'].append({
                    'campaign_id': campaign.id,
                    'name': campaign.name,
                    'error': str(e)
                })
    except Exception as e:
        logger.error(f"Error fetching email campaigns: {str(e)}")
        results['email_campaigns']['errors'].append({'error': str(e)})

    # Process SMS campaigns
    try:
        sms_campaigns = SMSCampaign.objects.filter(
            status='scheduled',
            scheduled_at__lte=now
        )

        for campaign in sms_campaigns:
            results['sms_campaigns']['processed'] += 1
            try:
                result = send_sms_campaign(campaign)
                if 'error' in result:
                    results['sms_campaigns']['failed'] += 1
                    results['sms_campaigns']['errors'].append({
                        'campaign_id': campaign.id,
                        'name': campaign.name,
                        'error': result['error']
                    })
                else:
                    results['sms_campaigns']['sent'] += result.get('sent', 0)
                    results['sms_campaigns']['failed'] += result.get('failed', 0)
            except Exception as e:
                logger.error(f"Error processing SMS campaign {campaign.id}: {str(e)}")
                results['sms_campaigns']['errors'].append({
                    'campaign_id': campaign.id,
                    'name': campaign.name,
                    'error': str(e)
                })
    except Exception as e:
        logger.error(f"Error fetching SMS campaigns: {str(e)}")
        results['sms_campaigns']['errors'].append({'error': str(e)})

    # Log summary
    logger.info(
        f"Campaign webhook processed: "
        f"Email: {results['email_campaigns']['processed']} campaigns, "
        f"{results['email_campaigns']['sent']} sent, "
        f"SMS: {results['sms_campaigns']['processed']} campaigns, "
        f"{results['sms_campaigns']['sent']} sent"
    )

    return JsonResponse({
        'status': 'success',
        'results': results
    })
