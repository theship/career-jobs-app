"""Database connection utilities."""

import asyncpg
from typing import Optional
import logging
from contextlib import asynccontextmanager

from .config import settings

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages database connection pool."""

    def __init__(self):
        """Initialize database connection."""
        self.pool: Optional[asyncpg.Pool] = None
        self._parse_supabase_url()

    def _parse_supabase_url(self):
        """Parse Supabase URL to get database connection string."""
        # Supabase URL format: https://[project-ref].supabase.co
        # Database URL format: postgresql://postgres.[project-ref]:password@aws-0-[region].pooler.supabase.com:6543/postgres

        # For now, we'll use the Supabase client for all DB operations
        # Direct DB connection would require the database URL from Supabase dashboard
        pass

    async def init_pool(self):
        """Initialize connection pool."""
        if self.pool is None:
            try:
                # This would need the actual database URL from Supabase
                # For Phase 2, we're using Supabase client instead of direct DB access
                logger.info(
                    "Database pool initialization skipped - using Supabase client"
                )
            except Exception as e:
                logger.error(f"Failed to initialize database pool: {e}")
                raise

    async def close_pool(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a database connection from the pool."""
        if self.pool is None:
            await self.init_pool()

        async with self.pool.acquire() as conn:
            yield conn


# Global database connection instance
db_connection = DatabaseConnection()


async def get_db_connection():
    """Dependency to get database connection."""
    # For now, return the connection object
    # In production, this would return an actual DB connection
    return db_connection


async def init_database():
    """Initialize database on application startup."""
    await db_connection.init_pool()


async def close_database():
    """Close database on application shutdown."""
    await db_connection.close_pool()
