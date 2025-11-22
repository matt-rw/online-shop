import base64
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

import qrcode
import qrcode.image.svg
from django_otp import user_has_device
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.util import random_hex


@login_required
def two_factor_setup(request):
    """
    Set up two-factor authentication for the user.
    Generates a QR code for Google Authenticator/Authy/etc.
    """
    user = request.user

    # Check if user already has 2FA enabled
    if user_has_device(user):
        messages.info(request, "You already have two-factor authentication enabled.")
        return redirect("admin_home")

    # Get or create TOTP device for user
    device, created = TOTPDevice.objects.get_or_create(
        user=user, name="default", defaults={"confirmed": False}
    )

    if request.method == "POST":
        token = request.POST.get("token", "").strip()

        if device.verify_token(token):
            device.confirmed = True
            device.save()
            messages.success(request, "Two-factor authentication has been enabled successfully!")
            return redirect("admin_home")
        else:
            messages.error(request, "Invalid verification code. Please try again.")

    # Generate QR code
    url = device.config_url
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()

    context = {
        "qr_code": img_str,
        "secret_key": device.key,
    }

    return render(request, "admin/two_factor_setup.html", context)


@login_required
def two_factor_verify(request):
    """
    Verify the 2FA token after login to access protected admin pages.
    """
    user = request.user

    # Check if user has 2FA enabled
    if not user_has_device(user):
        messages.warning(request, "You need to set up two-factor authentication first.")
        return redirect("two_factor_setup")

    # Check if already verified in this session
    if request.session.get("2fa_verified"):
        return redirect(request.GET.get("next", "admin_home"))

    if request.method == "POST":
        token = request.POST.get("token", "").strip()

        # Get user's TOTP device
        device = TOTPDevice.objects.filter(user=user, confirmed=True).first()

        if device and device.verify_token(token):
            # Mark session as 2FA verified
            request.session["2fa_verified"] = True
            messages.success(request, "Two-factor authentication successful!")
            next_url = request.GET.get("next", "admin_home")
            return redirect(next_url)
        else:
            messages.error(request, "Invalid verification code. Please try again.")

    return render(request, "admin/two_factor_verify.html")


@login_required
def two_factor_disable(request):
    """
    Disable two-factor authentication for the user.
    """
    if request.method == "POST":
        user = request.user
        TOTPDevice.objects.filter(user=user).delete()
        request.session.pop("2fa_verified", None)
        messages.success(request, "Two-factor authentication has been disabled.")
        return redirect("admin_home")

    return render(request, "admin/two_factor_disable.html")
