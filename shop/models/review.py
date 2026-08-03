from django.contrib.auth.models import User
from django.db import models


class ProductReview(models.Model):
    """Customer reviews for products."""
    product = models.ForeignKey(
        "shop.Product", on_delete=models.CASCADE, related_name="reviews"
    )
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=100, help_text="Reviewer display name")
    email = models.EmailField(blank=True)
    rating = models.PositiveIntegerField(help_text="1-5 stars")
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True, help_text="Auto-approved, can be hidden by admin")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "-created_at"], name="review_product_idx"),
        ]

    def __str__(self):
        return f"{self.name} — {self.rating}★ on {self.product.name}"
