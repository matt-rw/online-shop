"""
Geocoding utilities for converting addresses to coordinates.
Uses OpenStreetMap's Nominatim API (free, no API key required).
"""

import logging
import time
from functools import lru_cache

import requests

logger = logging.getLogger(__name__)

# Rate limiting: Nominatim requires max 1 request per second
_last_request_time = 0


def _rate_limit():
    """Ensure we don't exceed Nominatim's rate limit (1 req/sec)."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_request_time = time.time()


@lru_cache(maxsize=1000)
def geocode_address(city, region, postal_code, country='US'):
    """
    Geocode an address to latitude/longitude coordinates.

    Args:
        city: City name
        region: State/region code (e.g., 'IL', 'CA')
        postal_code: ZIP/postal code
        country: Country code (default 'US')

    Returns:
        tuple: (latitude, longitude) or None if geocoding fails
    """
    if not city and not postal_code:
        return None

    _rate_limit()

    # Build query - postal code is often most accurate
    query_parts = []
    if city:
        query_parts.append(city)
    if region:
        query_parts.append(region)
    if postal_code:
        query_parts.append(postal_code)
    if country:
        query_parts.append(country)

    query = ', '.join(query_parts)

    try:
        response = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'q': query,
                'format': 'json',
                'limit': 1,
            },
            headers={
                'User-Agent': 'BlueprintApparel/1.0 (admin dashboard)',
            },
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                logger.debug(f"Geocoded '{query}' to ({lat}, {lon})")
                return (lat, lon)

        logger.warning(f"Geocoding failed for '{query}': {response.status_code}")

    except requests.RequestException as e:
        logger.error(f"Geocoding request failed for '{query}': {e}")
    except (KeyError, ValueError, IndexError) as e:
        logger.error(f"Geocoding parse error for '{query}': {e}")

    return None


def geocode_address_async(address_id):
    """
    Geocode an address by ID (for use in background tasks).

    Args:
        address_id: The ID of the Address to geocode
    """
    from shop.models import Address

    try:
        address = Address.objects.get(id=address_id)
        if address.latitude is None or address.longitude is None:
            address.geocode()
    except Address.DoesNotExist:
        logger.warning(f"Address {address_id} not found for geocoding")
