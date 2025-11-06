from django.db import models


class EmailSubscription(models.Model):
    email = models.EmailField(unique=True)
    is_confirmed = models.BooleanField(default=False)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=50, default='site_form')

    # unsub_token = models.CharField(max_length=64, unique=True)
