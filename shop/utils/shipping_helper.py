"""
Shipping label generation utilities.
Supports multiple carriers and services.
"""
import logging
from decimal import Decimal
from typing import Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class ShippingService:
    """Base class for shipping service integrations."""

    def get_rates(self, order) -> List[Dict]:
        """Get shipping rates for an order."""
        raise NotImplementedError

    def create_label(self, order, rate_id: str) -> Dict:
        """Create a shipping label for an order."""
        raise NotImplementedError


class EasyPostService(ShippingService):
    """EasyPost shipping integration (multi-carrier)."""

    def __init__(self):
        try:
            import easypost

            self.easypost = easypost
            self.api_key = getattr(settings, "EASYPOST_API_KEY", None)
            if self.api_key:
                easypost.api_key = self.api_key
        except ImportError:
            logger.warning("EasyPost not installed. Run: pip install easypost")
            self.easypost = None

    def get_rates(self, order) -> List[Dict]:
        """Get shipping rates from all carriers via EasyPost."""
        if not self.easypost or not self.api_key:
            return []

        try:
            shipment = self._create_shipment(order)

            rates = []
            for rate in shipment.rates:
                rates.append(
                    {
                        "id": rate.id,
                        "carrier": rate.carrier,
                        "service": rate.service,
                        "rate": float(rate.rate),
                        "currency": rate.currency,
                        "delivery_days": rate.delivery_days,
                        "delivery_date": rate.delivery_date,
                        "provider": "easypost",
                    }
                )

            return sorted(rates, key=lambda x: x["rate"])

        except Exception as e:
            logger.error(f"Error getting EasyPost rates: {e}")
            return []

    def create_label(self, order, rate_id: str) -> Dict:
        """Create shipping label via EasyPost."""
        if not self.easypost or not self.api_key:
            raise Exception("EasyPost not configured")

        try:
            shipment = self._create_shipment(order)

            # Buy the selected rate
            selected_rate = next((r for r in shipment.rates if r.id == rate_id), None)
            if not selected_rate:
                # Fall back to cheapest rate
                selected_rate = shipment.lowest_rate()

            shipment.buy(rate=selected_rate)

            return {
                "tracking_number": shipment.tracker.tracking_code,
                "carrier": shipment.selected_rate.carrier,
                "label_url": shipment.postage_label.label_url,
                "cost": float(shipment.selected_rate.rate),
            }

        except Exception as e:
            logger.error(f"Error creating EasyPost label: {e}")
            raise

    def _create_shipment(self, order):
        """Create EasyPost shipment object."""
        return self.easypost.Shipment.create(
            to_address={
                "name": order.shipping_address.full_name,
                "street1": order.shipping_address.line1,
                "street2": order.shipping_address.line2 or "",
                "city": order.shipping_address.city,
                "state": order.shipping_address.region,
                "zip": order.shipping_address.postal_code,
                "country": order.shipping_address.country,
                "email": order.shipping_address.email or order.email,
            },
            from_address=self._get_warehouse_address(),
            parcel=self._calculate_parcel(order),
        )

    def _get_warehouse_address(self) -> Dict:
        """Get warehouse/sender address from settings."""
        return {
            "name": getattr(settings, "WAREHOUSE_NAME", "Blueprint Apparel"),
            "street1": getattr(settings, "WAREHOUSE_ADDRESS_LINE1", "123 Fashion Ave"),
            "street2": getattr(settings, "WAREHOUSE_ADDRESS_LINE2", ""),
            "city": getattr(settings, "WAREHOUSE_CITY", "New York"),
            "state": getattr(settings, "WAREHOUSE_STATE", "NY"),
            "zip": getattr(settings, "WAREHOUSE_ZIP", "10001"),
            "country": getattr(settings, "WAREHOUSE_COUNTRY", "US"),
            "phone": getattr(settings, "WAREHOUSE_PHONE", ""),
        }

    def _calculate_parcel(self, order) -> Dict:
        """Calculate package dimensions and weight for order."""
        # TODO: Calculate based on actual order items
        # For now, use default small package
        return {
            "length": 10,  # inches
            "width": 8,
            "height": 4,
            "weight": 16,  # ounces
        }


class PirateShipService(ShippingService):
    """Pirate Ship integration (USPS only, free service)."""

    # Note: Pirate Ship doesn't have a public API yet
    # This is a placeholder for future implementation
    # Currently, you'd use their website manually

    def get_rates(self, order) -> List[Dict]:
        """Pirate Ship doesn't have public API for rate quotes."""
        return [
            {
                "id": "pirate_ship_manual",
                "carrier": "USPS",
                "service": "Manual entry via pirateship.com",
                "rate": 0.0,
                "currency": "USD",
                "delivery_days": None,
                "provider": "pirate_ship",
                "note": "Create label manually at pirateship.com (free)",
            }
        ]

    def create_label(self, order, rate_id: str) -> Dict:
        """Pirate Ship requires manual label creation."""
        raise NotImplementedError(
            "Pirate Ship requires manual label creation at pirateship.com"
        )


# Service registry
AVAILABLE_SERVICES = {
    "easypost": EasyPostService,
    "pirate_ship": PirateShipService,
}


def get_shipping_rates(order) -> List[Dict]:
    """
    Get shipping rates from all configured services.

    Returns a list of rate options sorted by price.
    """
    all_rates = []

    for service_name, service_class in AVAILABLE_SERVICES.items():
        try:
            service = service_class()
            rates = service.get_rates(order)
            all_rates.extend(rates)
        except Exception as e:
            logger.error(f"Error getting rates from {service_name}: {e}")

    return sorted(all_rates, key=lambda x: x.get("rate", 999))


def create_shipping_label(order, rate_id: str, provider: str) -> Dict:
    """
    Create a shipping label using the specified provider and rate.

    Args:
        order: Order object
        rate_id: ID of the selected rate
        provider: Provider name (e.g., 'easypost', 'pirate_ship')

    Returns:
        Dict with tracking_number, carrier, label_url, cost
    """
    service_class = AVAILABLE_SERVICES.get(provider)
    if not service_class:
        raise ValueError(f"Unknown shipping provider: {provider}")

    service = service_class()
    result = service.create_label(order, rate_id)

    # Update order with shipping info
    order.tracking_number = result["tracking_number"]
    order.carrier = result["carrier"]
    order.label_url = result["label_url"]
    order.save()

    logger.info(
        f"Created shipping label for order {order.id}: "
        f"{result['carrier']} {result['tracking_number']}"
    )

    return result


def manual_tracking_entry(order, tracking_number: str, carrier: str) -> Dict:
    """
    Manually enter tracking info (for services without API like Pirate Ship).

    Args:
        order: Order object
        tracking_number: Tracking number from carrier
        carrier: Carrier name (USPS, UPS, FedEx, etc.)

    Returns:
        Dict with tracking info
    """
    order.tracking_number = tracking_number
    order.carrier = carrier
    order.save()

    logger.info(
        f"Manual tracking entry for order {order.id}: {carrier} {tracking_number}"
    )

    return {
        "tracking_number": tracking_number,
        "carrier": carrier,
        "label_url": None,
        "cost": 0.0,
    }
