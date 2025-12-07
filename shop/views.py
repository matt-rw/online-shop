import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
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


def coming_soon(request):
    """Simple coming soon page for footer links."""
    return render(request, "home/coming_soon.html")


def about(request):
    """About page with Our Story and Foundation Line sections."""
    return render(request, "home/about.html")


def privacy(request):
    """Privacy Policy page."""
    return render(request, "home/privacy.html")


def terms(request):
    """Terms of Service page."""
    return render(request, "home/terms.html")


@login_required(login_url='account_login')
def account(request):
    """User account page - requires customer login."""
    # Get user's orders, profile, and addresses
    orders = []
    addresses = []
    profile = None

    if request.user.is_authenticated:
        # Handle POST requests
        if request.method == "POST":
            form_type = request.POST.get("form_type")

            if form_type == "details":
                # Update user details
                from django.contrib import messages

                request.user.first_name = request.POST.get("first_name", "")
                request.user.last_name = request.POST.get("last_name", "")
                request.user.save()

                # Update or create profile with phone
                try:
                    from .models import UserProfile
                    profile, created = UserProfile.objects.get_or_create(user=request.user)
                    profile.phone = request.POST.get("phone", "")
                    profile.save()
                except Exception:
                    pass

                messages.success(request, "Your details have been updated.")
                return redirect("shop:account")

            elif form_type == "address":
                # Add new address
                from django.contrib import messages

                try:
                    from .models import SavedAddress
                    is_default = request.POST.get("is_default") == "on"

                    # If setting as default, unset other defaults
                    if is_default:
                        SavedAddress.objects.filter(user=request.user, is_default_shipping=True).update(is_default_shipping=False)

                    SavedAddress.objects.create(
                        user=request.user,
                        label=request.POST.get("label", ""),
                        full_name=request.user.get_full_name() or request.user.email,
                        line1=request.POST.get("street", ""),
                        city=request.POST.get("city", ""),
                        region=request.POST.get("state", ""),
                        postal_code=request.POST.get("zip_code", ""),
                        country="US",
                        is_default_shipping=is_default,
                    )
                    messages.success(request, "Address added successfully.")
                except Exception as e:
                    logger.error(f"Error adding address: {e}")
                    messages.error(request, "Failed to add address.")

                return redirect("shop:account")

            elif form_type == "delete_address":
                # Delete address
                from django.contrib import messages

                try:
                    from .models import SavedAddress
                    address_id = request.POST.get("address_id")
                    SavedAddress.objects.filter(id=address_id, user=request.user).delete()
                    messages.success(request, "Address deleted.")
                except Exception as e:
                    logger.error(f"Error deleting address: {e}")
                    messages.error(request, "Failed to delete address.")

                return redirect("shop:account")

            elif form_type == "password":
                # Handle password change inline
                from django.contrib import messages
                from django.contrib.auth import update_session_auth_hash

                old_password = request.POST.get("oldpassword", "")
                new_password1 = request.POST.get("password1", "")
                new_password2 = request.POST.get("password2", "")

                # Validate old password
                if not request.user.check_password(old_password):
                    messages.error(request, "Your current password is incorrect.")
                    return redirect("shop:account")

                # Validate new passwords match
                if new_password1 != new_password2:
                    messages.error(request, "New passwords do not match.")
                    return redirect("shop:account")

                # Validate password length
                if len(new_password1) < 8:
                    messages.error(request, "Password must be at least 8 characters.")
                    return redirect("shop:account")

                # Update password
                request.user.set_password(new_password1)
                request.user.save()

                # Keep user logged in after password change
                update_session_auth_hash(request, request.user)

                messages.success(request, "Your password has been updated.")
                return redirect("shop:account")

        # Try to get orders
        try:
            from .models import Order
            orders = Order.objects.filter(user=request.user).order_by('-created_at')[:5]
        except Exception:
            pass

        # Try to get profile
        try:
            from .models import UserProfile
            profile = UserProfile.objects.filter(user=request.user).first()
        except Exception:
            pass

        # Try to get addresses
        try:
            from .models import SavedAddress
            addresses = SavedAddress.objects.filter(user=request.user)
        except Exception:
            pass

    # Get email from allauth if not on user model
    user_email = request.user.email
    if not user_email and request.user.is_authenticated:
        try:
            from allauth.account.models import EmailAddress
            email_obj = EmailAddress.objects.filter(user=request.user, primary=True).first()
            if email_obj:
                user_email = email_obj.email
        except Exception:
            pass

    context = {
        "user": request.user,
        "user_email": user_email,
        "orders": orders,
        "profile": profile,
        "addresses": addresses,
    }

    return render(request, "shop/account.html", context)


def product_detail(request, slug):
    """Product detail page."""
    import json
    from django.shortcuts import get_object_or_404

    from .models import Product

    product = get_object_or_404(Product, slug=slug, is_active=True)

    # Get all variants for this product with related size and color
    variants = product.variants.filter(is_active=True).select_related("size", "color")

    # Build variant data map for JavaScript (size -> variant info)
    # This allows the frontend to look up stock and variant ID by size
    variant_data = {}
    for variant in variants:
        size_code = variant.size.code if variant.size else "one-size"
        color_name = variant.color.name if variant.color else "default"
        key = f"{size_code}_{color_name}"
        variant_data[key] = {
            "id": variant.id,
            "stock": variant.stock_quantity,
            "price": str(variant.price),
        }

    # Collect unique sizes and colors from variants
    sizes = []
    colors = []
    seen_sizes = set()
    seen_colors = set()

    # Calculate total stock across all variants
    total_stock = sum(v.stock_quantity for v in variants)

    for variant in variants:
        if variant.size and variant.size.code not in seen_sizes:
            sizes.append({
                "code": variant.size.code,
                "label": variant.size.label or variant.size.code,
                "available": variant.stock_quantity > 0,
                "stock": variant.stock_quantity,
            })
            seen_sizes.add(variant.size.code)
        if variant.color and variant.color.name not in seen_colors:
            colors.append({
                "name": variant.color.name,
                "hex": "#000000"  # Default, could be extended to store hex in model
            })
            seen_colors.add(variant.color.name)

    # Collect all images from variants
    images = []
    for variant in variants:
        if variant.images:
            images.extend(variant.images)

    # If no variant images, use placeholder based on product category
    if not images:
        if product.category_legacy and "bottom" in product.category_legacy.lower():
            images = ["/static/images/white_bg_bottom.webp"]
        elif product.slug and "pants" in product.slug.lower():
            images = ["/static/images/white_bg_bottom.webp"]
        else:
            images = ["/static/images/white_bg_top.webp"]

    main_image = images[0] if images else "/static/images/white_bg_top.webp"

    # Get default variant (first active one with stock, or just first)
    default_variant = None
    for v in variants:
        if v.stock_quantity > 0:
            default_variant = v
            break
    if not default_variant:
        default_variant = variants.first()

    default_variant_id = default_variant.id if default_variant else None
    default_variant_stock = default_variant.stock_quantity if default_variant else 0

    context = {
        "product": product,
        "variants": variants,
        "sizes": sizes,
        "colors": colors,
        "images": images,
        "main_image": main_image,
        "default_variant_id": default_variant_id,
        "default_variant_stock": default_variant_stock,
        "total_stock": total_stock,
        "variant_data_json": json.dumps(variant_data),
    }

    return render(request, "shop/product_detail.html", context)


def shop(request):
    """Shop catalog page - lists all products with filtering."""
    from django.db.models import Prefetch
    from .models import Category, Product, ProductVariant

    # Get filter parameters
    category_slug = request.GET.get("category")
    sort_by = request.GET.get("sort", "newest")

    # Base queryset - active products with prefetched variants
    products = Product.objects.filter(is_active=True).prefetch_related(
        Prefetch(
            "variants",
            queryset=ProductVariant.objects.filter(is_active=True),
            to_attr="active_variants"
        )
    )

    # Filter by category if specified
    selected_category = None
    if category_slug:
        selected_category = Category.objects.filter(slug=category_slug).first()
        if selected_category:
            products = products.filter(category_obj=selected_category)

    # Sort products
    if sort_by == "price_low":
        products = products.order_by("base_price")
    elif sort_by == "price_high":
        products = products.order_by("-base_price")
    elif sort_by == "name":
        products = products.order_by("name")
    else:  # newest (default)
        products = products.order_by("-created_at")

    # Get all categories for filter
    categories = Category.objects.all()

    # Build product data with images (no extra queries due to prefetch)
    product_list = []
    for product in products:
        # Get first variant image or use placeholder
        first_variant = product.active_variants[0] if product.active_variants else None
        if first_variant and first_variant.images:
            image = first_variant.images[0]
        elif "pants" in product.slug.lower() or "bottom" in product.name.lower():
            image = "/static/images/white_bg_bottom.webp"
        else:
            image = "/static/images/white_bg_top.webp"

        product_list.append({
            "product": product,
            "image": image,
            "variant_count": len(product.active_variants),
        })

    context = {
        "products": product_list,
        "categories": categories,
        "selected_category": selected_category,
        "sort_by": sort_by,
        "product_count": len(product_list),
    }

    return render(request, "shop/shop.html", context)


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
