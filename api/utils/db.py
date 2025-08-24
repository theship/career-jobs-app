"""
Database connection and Supabase client utilities
"""
from typing import Optional
from functools import lru_cache
import logging
from supabase import create_client, Client
from api.utils.config import get_settings

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """Manage Supabase database connection"""
    
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[Client] = None
        self._service_client: Optional[Client] = None
    
    @property
    def client(self) -> Client:
        """Get Supabase client with anon key (for client-side operations)"""
        if self._client is None:
            self._client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_anon_key
            )
            logger.info("Created Supabase client with anon key")
        return self._client
    
    @property
    def service_client(self) -> Client:
        """Get Supabase client with service role key (for server-side operations)"""
        if self._service_client is None:
            self._service_client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_service_role_key
            )
            logger.info("Created Supabase client with service role key")
        return self._service_client
    
    def get_client(self, use_service_role: bool = False) -> Client:
        """
        Get appropriate Supabase client
        
        Args:
            use_service_role: If True, use service role key (bypasses RLS)
            
        Returns:
            Supabase client
        """
        return self.service_client if use_service_role else self.client
    
    async def health_check(self) -> bool:
        """
        Check database connection health
        
        Returns:
            True if connection is healthy
        """
        try:
            # Try a simple query
            result = self.client.table("app_user").select("id").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

# Singleton instance
@lru_cache()
def get_db() -> DatabaseConnection:
    """Get singleton database connection"""
    return DatabaseConnection()

# Dependency for FastAPI routes
async def get_supabase_client() -> Client:
    """
    FastAPI dependency to get Supabase client
    
    Returns:
        Supabase client with anon key
    """
    return get_db().client

async def get_supabase_service_client() -> Client:
    """
    FastAPI dependency to get Supabase service client
    
    Returns:
        Supabase client with service role key
    """
    return get_db().service_client