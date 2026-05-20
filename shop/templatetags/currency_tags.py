"""
Custom template tags for currency formatting.
"""
from decimal import Decimal, ROUND_HALF_UP

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def price(context, amount, show_code=False):
    """
    Format a price in the user's selected currency.

    Usage:
        {% load currency_tags %}
        {% price product.base_price %}          -> $45.00 or €41.40
        {% price product.base_price show_code=True %} -> $45.00 USD or €41.40 EUR

    Args:
        amount: The price in USD (base currency)
        show_code: Whether to append the currency code
    """
    if amount is None:
        return ""

    currency = context.get('current_currency')

    if not currency:
        # Fallback to basic USD formatting if no currency context
        return f"${Decimal(str(amount)):.2f}"

    formatted = currency.format_price(amount)

    if show_code:
        return f"{formatted} {currency.code}"

    return formatted


@register.simple_tag(takes_context=True)
def convert_price(context, amount):
    """
    Convert a price to the user's selected currency without formatting.
    Returns the numeric value only (useful for JavaScript).

    Usage:
        {% load currency_tags %}
        <span data-price="{% convert_price product.base_price %}">
    """
    if amount is None:
        return "0"

    currency = context.get('current_currency')

    if not currency:
        return str(amount)

    converted = Decimal(str(amount)) * currency.exchange_rate
    quantize_str = '0.' + '0' * currency.decimal_places if currency.decimal_places > 0 else '1'
    rounded = converted.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP)

    return str(rounded)


@register.simple_tag(takes_context=True)
def currency_symbol(context):
    """
    Get the current currency symbol.

    Usage:
        {% load currency_tags %}
        {{ currency_symbol }}
    """
    currency = context.get('current_currency')
    if currency:
        return currency.symbol
    return "$"


@register.simple_tag(takes_context=True)
def currency_code(context):
    """
    Get the current currency code.

    Usage:
        {% load currency_tags %}
        {{ currency_code }}
    """
    currency = context.get('current_currency')
    if currency:
        return currency.code
    return "USD"


@register.inclusion_tag('partials/currency_selector.html', takes_context=True)
def currency_selector(context):
    """
    Render the currency selector dropdown.

    Usage:
        {% load currency_tags %}
        {% currency_selector %}
    """
    return {
        'current_currency': context.get('current_currency'),
        'available_currencies': context.get('available_currencies', []),
        'request': context.get('request'),
    }
