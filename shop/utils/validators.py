"""
Validation utilities for the shop application.
"""

import logging
from typing import Optional, Tuple

import phonenumbers
from phonenumbers import NumberParseException

logger = logging.getLogger(__name__)


def validate_and_format_phone_number(
    phone_number: str, default_region: str = "US"
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate and format a phone number to E.164 format.

    Args:
        phone_number: The phone number to validate (can be in various formats)
        default_region: Default country code if not provided (default: US)

    Returns:
        Tuple of (is_valid, formatted_number, error_message)
        - is_valid: True if the number is valid
        - formatted_number: The E.164 formatted number (e.g., +12345678900) or None
        - error_message: Error message if validation failed, or None

    Examples:
        >>> validate_and_format_phone_number("(555) 123-4567")
        (True, "+15551234567", None)

        >>> validate_and_format_phone_number("invalid")
        (False, None, "Invalid phone number format")
    """
    if not phone_number or not phone_number.strip():
        return False, None, "Phone number is required"

    try:
        # Parse the phone number
        parsed = phonenumbers.parse(phone_number, default_region)

        # Validate the parsed number
        if not phonenumbers.is_valid_number(parsed):
            return False, None, "Invalid phone number"

        # Format to E.164 (international format)
        formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

        logger.debug(f"Successfully validated phone number: {formatted}")
        return True, formatted, None

    except NumberParseException as e:
        error_msg = f"Invalid phone number format: {str(e)}"
        logger.warning(error_msg)
        return False, None, error_msg
    except Exception as e:
        error_msg = f"Error validating phone number: {str(e)}"
        logger.error(error_msg)
        return False, None, error_msg


def is_phone_number_valid(phone_number: str, default_region: str = "US") -> bool:
    """
    Quick check if a phone number is valid.

    Args:
        phone_number: The phone number to validate
        default_region: Default country code if not provided

    Returns:
        True if valid, False otherwise
    """
    is_valid, _, _ = validate_and_format_phone_number(phone_number, default_region)
    return is_valid
