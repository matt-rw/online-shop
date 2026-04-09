"""
Custom template filters for JSON serialization.
"""
import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='to_json')
def to_json(value):
    """
    Safely serialize a Python object to JSON for use in HTML attributes.

    Usage: data-images='{{ product.images|to_json }}'

    This properly handles Python lists/dicts that would otherwise render
    with single quotes (breaking JSON.parse in JavaScript).
    """
    if value is None:
        return '[]'
    try:
        return mark_safe(json.dumps(value))
    except (TypeError, ValueError):
        return '[]'
