"""
Common imports and utilities for admin views.
"""

import base64
import csv
import io
import json
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

import pytz

from shop.decorators import two_factor_required
from shop.models import (
    Address,
    Bundle,
    BundleItem,
    Campaign,
    CampaignMessage,
    Category,
    ConnectionLog,
    CustomAttribute,
    CustomAttributeValue,
    Discount,
    EmailCampaign,
    EmailLog,
    EmailSubscription,
    EmailTemplate,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    ProductVariant,
    Shipment,
    ShipmentItem,
    SiteSettings,
    SMSCampaign,
    SMSLog,
    SMSSubscription,
    SMSTemplate,
    Size,
    Color,
    UserProfile,
)
from shop.models.settings import QuickLink
from shop.models.bug_report import BugReport
from shop.models.analytics import PageView, VisitorSession
from shop.models.messaging import QuickMessage

User = get_user_model()

# Central time zone for display
CST = pytz.timezone("America/Chicago")


def get_cst_time():
    """Get current time in Central time zone."""
    return timezone.now().astimezone(CST)
