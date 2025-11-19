import logging
from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.contrib import messages

from .forms import SubscribeForm
from .models import EmailSubscription

logger = logging.getLogger(__name__)


def subscribe(request):
    if request.method == 'POST':
        form = SubscribeForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data

            try:
                # Populate if email is new
                sub, created = EmailSubscription.objects.get_or_create(
                    email=data['email']
                )

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

                return redirect('/#subscribe')

            except Exception as e:
                logger.error(f"Error creating subscription: {e}")
                messages.error(request, "Something went wrong. Please try again.")
                return redirect('/#subscribe')

        else:
            logger.warning(f"Invalid subscription form submission: {form.errors}")
            messages.error(request, "Please enter a valid email address.")
            return redirect('/#subscribe')

    # GET request
    form = SubscribeForm()
    return render(request, 'home/home_page.html', {'form': form})


def subscribe_sms(request):
    """Handle SMS subscription sign-ups"""
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', '').strip()

        if not phone_number:
            messages.error(request, "Please enter a phone number.")
            return redirect('/#subscribe')

        # Normalize phone number to E.164 format if needed
        if not phone_number.startswith('+'):
            # Assume US number if no country code
            phone_number = '+1' + phone_number.replace('-', '').replace('(', '').replace(')', '').replace(' ', '')

        try:
            from shop.models import SMSSubscription
            from shop.utils.twilio_helper import trigger_auto_send

            # Create or get subscription
            subscription, created = SMSSubscription.objects.get_or_create(
                phone_number=phone_number,
                defaults={'source': 'site_form'}
            )

            if created:
                logger.info(f"New SMS subscription: {subscription.phone_number}")

                # Trigger automatic welcome message if configured
                trigger_auto_send('on_subscribe', subscription)

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
                    messages.success(request, "Welcome back! You're now resubscribed to SMS updates.")

            return redirect('/#subscribe')

        except Exception as e:
            logger.error(f"Error creating SMS subscription: {e}")
            messages.error(request, "Something went wrong. Please try again.")
            return redirect('/#subscribe')

    return redirect('/#subscribe')


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
