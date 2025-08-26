"""
Database utilities for API endpoints
"""

from typing import Optional

from supabase.lib.client_options import ClientOptions

from api.utils.config import get_settings
from supabase import Client, create_client

# Cached Supabase clients
_supabase_client: Optional[Client] = None
_supabase_service_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get or create a Supabase client instance (uses anon key, respects RLS)

    Returns:
        Supabase client
    """
    global _supabase_client

    if _supabase_client is None:
        settings = get_settings()
        _supabase_client = create_client(
            settings.supabase_url, settings.supabase_anon_key
        )

    return _supabase_client


def get_supabase_service_client() -> Client:
    """
    Get or create a Supabase service client instance (bypasses RLS)

    Returns:
        Supabase service client
    """
    global _supabase_service_client

    if _supabase_service_client is None:
        settings = get_settings()
        _supabase_service_client = create_client(
            settings.supabase_url, settings.supabase_service_role_key
        )

    return _supabase_service_client


def get_authenticated_supabase_client(token: str) -> Client:
    """
    Create a Supabase client authenticated with user's JWT token.

    This ensures that Row Level Security (RLS) policies are properly enforced
    based on the authenticated user's permissions.

    Args:
        token: User's JWT token from the Authorization header

    Returns:
        Authenticated Supabase client
    """
    settings = get_settings()

    # Create client options with auth header
    options = ClientOptions()
    options.headers = {"Authorization": f"Bearer {token}"}

    # Create a new client with user's JWT
    return create_client(
        settings.supabase_url, settings.supabase_anon_key, options=options
    )


# Alias for compatibility with existing code
get_db_connection = get_supabase_client
