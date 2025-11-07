from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

User = get_user_model()


class UserProfile(models.Model):
    """
    Extended user profile for storing additional user information.
    Automatically created when a user signs up.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # Optional profile fields
    phone_number = models.CharField(max_length=20, blank=True)

    # Stripe customer ID for payment processing
    stripe_customer_id = models.CharField(max_length=255, blank=True, db_index=True)

    # Marketing preferences
    marketing_emails = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user.email}"


class SavedAddress(models.Model):
    """
    Saved addresses for quick checkout.
    Users can have multiple saved addresses.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_addresses')

    label = models.CharField(
        max_length=50,
        blank=True,
        help_text="E.g., 'Home', 'Work', 'Mom's House'"
    )

    full_name = models.CharField(max_length=120)
    line1 = models.CharField(max_length=200, verbose_name="Address Line 1")
    line2 = models.CharField(max_length=200, blank=True, verbose_name="Address Line 2")
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True, verbose_name="State/Province")
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2, default='US', help_text="2-letter country code")

    is_default_shipping = models.BooleanField(default=False)
    is_default_billing = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default_shipping', '-created_at']
        verbose_name_plural = "Saved addresses"

    def __str__(self):
        label = f" ({self.label})" if self.label else ""
        return f"{self.full_name} - {self.city}, {self.region}{label}"

    def save(self, *args, **kwargs):
        # If this is set as default, unset other defaults for this user
        if self.is_default_shipping:
            SavedAddress.objects.filter(
                user=self.user,
                is_default_shipping=True
            ).exclude(pk=self.pk).update(is_default_shipping=False)

        if self.is_default_billing:
            SavedAddress.objects.filter(
                user=self.user,
                is_default_billing=True
            ).exclude(pk=self.pk).update(is_default_billing=False)

        super().save(*args, **kwargs)


# Signal to automatically create UserProfile when a User is created
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile whenever a new User is created."""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile whenever the User is saved."""
    if hasattr(instance, 'profile'):
        instance.profile.save()
