from django.db import models
from django.utils.text import slugify


class Lookbook(models.Model):
    """
    A lookbook/collection showcase with multiple pages.
    Supports multiple lookbooks (seasonal, themed) with one featured at a time.
    """
    title = models.CharField(
        max_length=200,
        help_text="e.g., 'Spring 2026', 'Fall Collection'"
    )
    slug = models.SlugField(
        unique=True,
        blank=True,
        help_text="URL-friendly version of title (auto-generated)"
    )
    description = models.TextField(
        blank=True,
        help_text="Brief description of this lookbook"
    )
    cover_image = models.URLField(
        blank=True,
        help_text="Cover image URL for listings"
    )
    pages = models.JSONField(
        default=list,
        blank=True,
        help_text="Lookbook pages. Each page has: image_url, title, description, position_x, position_y, zoom"
    )
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Lookbook settings: transition_type, etc."
    )
    is_published = models.BooleanField(
        default=False,
        help_text="Whether this lookbook is visible to the public"
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="The featured lookbook is shown at /shop/lookbook/"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = []
        if self.is_featured:
            status.append("Featured")
        if self.is_published:
            status.append("Published")
        else:
            status.append("Draft")
        return f"{self.title} ({', '.join(status)})"

    def save(self, *args, **kwargs):
        # Auto-generate slug if not provided
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Lookbook.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        # If this is being set as featured, unfeature others
        if self.is_featured:
            Lookbook.objects.filter(is_featured=True).exclude(pk=self.pk).update(is_featured=False)

        super().save(*args, **kwargs)

    @classmethod
    def get_featured(cls):
        """Get the currently featured lookbook."""
        return cls.objects.filter(is_featured=True, is_published=True).first()

    @property
    def page_count(self):
        return len(self.pages) if self.pages else 0
