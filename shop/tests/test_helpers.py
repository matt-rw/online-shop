"""
Test helpers and utilities.
"""
from django.contrib.auth import get_user_model

User = get_user_model()


def create_test_user(email='test@example.com', password='testpass123', **kwargs):
    """
    Helper to create a test user with email.
    Django's default User model requires username, so we use email as username.
    """
    username = kwargs.pop('username', email.split('@')[0])
    return User.objects.create_user(
        username=username,
        email=email,
        password=password,
        **kwargs
    )
