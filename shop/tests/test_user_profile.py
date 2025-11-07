"""
Tests for user profile and saved addresses.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from shop.models import UserProfile, SavedAddress
from .test_helpers import create_test_user

User = get_user_model()


class UserProfileTestCase(TestCase):
    """Test cases for UserProfile model."""

    def test_user_profile_created_on_user_creation(self):
        """Test that UserProfile is automatically created when User is created."""
        user = create_test_user()

        # Profile should exist
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsInstance(user.profile, UserProfile)

    def test_user_profile_fields(self):
        """Test UserProfile fields."""
        user = create_test_user()

        profile = user.profile
        profile.phone_number = '555-1234'
        profile.stripe_customer_id = 'cus_test123'
        profile.marketing_emails = False
        profile.save()

        profile.refresh_from_db()
        self.assertEqual(profile.phone_number, '555-1234')
        self.assertEqual(profile.stripe_customer_id, 'cus_test123')
        self.assertFalse(profile.marketing_emails)

    def test_user_profile_str(self):
        """Test UserProfile string representation."""
        user = create_test_user()

        profile_str = str(user.profile)
        self.assertIn('test@example.com', profile_str)


class SavedAddressTestCase(TestCase):
    """Test cases for SavedAddress model."""

    def setUp(self):
        """Set up test data."""
        self.user = create_test_user()

    def test_create_saved_address(self):
        """Test creating a saved address."""
        address = SavedAddress.objects.create(
            user=self.user,
            label='Home',
            full_name='John Doe',
            line1='123 Main St',
            line2='Apt 4B',
            city='Chicago',
            region='IL',
            postal_code='60601',
            country='US'
        )

        self.assertEqual(address.user, self.user)
        self.assertEqual(address.label, 'Home')
        self.assertEqual(address.city, 'Chicago')

    def test_saved_address_str(self):
        """Test SavedAddress string representation."""
        address = SavedAddress.objects.create(
            user=self.user,
            label='Home',
            full_name='John Doe',
            line1='123 Main St',
            city='Chicago',
            region='IL',
            postal_code='60601',
            country='US'
        )

        address_str = str(address)
        self.assertIn('John Doe', address_str)
        self.assertIn('Chicago', address_str)
        self.assertIn('Home', address_str)

    def test_default_shipping_address(self):
        """Test setting default shipping address."""
        address1 = SavedAddress.objects.create(
            user=self.user,
            label='Home',
            full_name='John Doe',
            line1='123 Main St',
            city='Chicago',
            region='IL',
            postal_code='60601',
            country='US',
            is_default_shipping=True
        )

        # Create another address as default
        address2 = SavedAddress.objects.create(
            user=self.user,
            label='Work',
            full_name='John Doe',
            line1='456 Office Blvd',
            city='Chicago',
            region='IL',
            postal_code='60602',
            country='US',
            is_default_shipping=True
        )

        # First address should no longer be default
        address1.refresh_from_db()
        self.assertFalse(address1.is_default_shipping)
        self.assertTrue(address2.is_default_shipping)

    def test_default_billing_address(self):
        """Test setting default billing address."""
        address1 = SavedAddress.objects.create(
            user=self.user,
            label='Home',
            full_name='John Doe',
            line1='123 Main St',
            city='Chicago',
            region='IL',
            postal_code='60601',
            country='US',
            is_default_billing=True
        )

        address2 = SavedAddress.objects.create(
            user=self.user,
            label='Work',
            full_name='John Doe',
            line1='456 Office Blvd',
            city='Chicago',
            region='IL',
            postal_code='60602',
            country='US',
            is_default_billing=True
        )

        address1.refresh_from_db()
        self.assertFalse(address1.is_default_billing)
        self.assertTrue(address2.is_default_billing)

    def test_multiple_saved_addresses(self):
        """Test user can have multiple saved addresses."""
        address1 = SavedAddress.objects.create(
            user=self.user,
            label='Home',
            full_name='John Doe',
            line1='123 Main St',
            city='Chicago',
            region='IL',
            postal_code='60601',
            country='US'
        )

        address2 = SavedAddress.objects.create(
            user=self.user,
            label='Work',
            full_name='John Doe',
            line1='456 Office Blvd',
            city='Chicago',
            region='IL',
            postal_code='60602',
            country='US'
        )

        self.assertEqual(self.user.saved_addresses.count(), 2)

    def test_saved_address_ordering(self):
        """Test saved addresses are ordered by default then created date."""
        address1 = SavedAddress.objects.create(
            user=self.user,
            label='Work',
            full_name='John Doe',
            line1='456 Office Blvd',
            city='Chicago',
            region='IL',
            postal_code='60602',
            country='US',
            is_default_shipping=False
        )

        address2 = SavedAddress.objects.create(
            user=self.user,
            label='Home',
            full_name='John Doe',
            line1='123 Main St',
            city='Chicago',
            region='IL',
            postal_code='60601',
            country='US',
            is_default_shipping=True
        )

        addresses = list(self.user.saved_addresses.all())

        # Default should come first
        self.assertEqual(addresses[0].label, 'Home')
        self.assertEqual(addresses[1].label, 'Work')
