"""
DEPRECATED: Use sms_helper.py instead.

This module is kept for backwards compatibility.
All functions are re-exported from sms_helper.py.
"""
import warnings

warnings.warn(
    "twilio_helper is deprecated. Use sms_helper instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export all functions from the new module
from .sms_helper import (
    send_sms,
    send_from_template,
    send_campaign,
    trigger_auto_send,
    handle_opt_out,
    handle_opt_in,
    get_sms_provider,
)

__all__ = [
    "send_sms",
    "send_from_template",
    "send_campaign",
    "trigger_auto_send",
    "handle_opt_out",
    "handle_opt_in",
    "get_sms_provider",
]
