"""
Database utilities for API endpoints
"""

from typing import Optional

from api.utils.config import get_settings
from supabase import Client, create_client

# Cached Supabase client
_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get or create a Supabase client instance

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


# Alias for compatibility with existing code
get_db_connection = get_supabase_client
