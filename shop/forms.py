from django import forms

from .models import EmailSubscription


class SubscribeForm(forms.ModelForm):
    class Meta:
        model = EmailSubscription
        fields = ["email"]
