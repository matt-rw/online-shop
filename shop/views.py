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
