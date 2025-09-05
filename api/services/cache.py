"""
Caching service using Redis for expensive operations
"""

import hashlib
import json
import logging
from typing import Any, Optional

from api.utils.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class CacheService:
    """
    Service for caching expensive operations using Redis
    """

    def __init__(self, namespace: str = "cache"):
        """
        Initialize cache service

        Args:
            namespace: Key prefix for this cache instance
        """
        self.redis = get_redis_client()
        self.namespace = namespace

    def _make_key(self, key: str) -> str:
        """Create namespaced cache key"""
        return f"{self.namespace}:{key}"

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        try:
            full_key = self._make_key(key)
            value = self.redis.get(full_key)

            if value:
                logger.debug(f"Cache hit for key: {key}")
                return json.loads(value)

            logger.debug(f"Cache miss for key: {key}")
            return None

        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = 3600,
    ) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds (default 1 hour)

        Returns:
            True if successful
        """
        try:
            full_key = self._make_key(key)
            serialized = json.dumps(value)

            if ttl_seconds:
                result = self.redis.setex(full_key, ttl_seconds, serialized)
            else:
                result = self.redis.set(full_key, serialized)

            logger.debug(f"Cache set for key: {key} (TTL: {ttl_seconds}s)")
            return bool(result)

        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete value from cache

        Args:
            key: Cache key

        Returns:
            True if key existed and was deleted
        """
        try:
            full_key = self._make_key(key)
            result = self.redis.delete(full_key)

            if result:
                logger.debug(f"Cache deleted for key: {key}")

            return bool(result)

        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    def clear_namespace(self) -> int:
        """
        Clear all keys in this namespace

        Returns:
            Number of keys deleted
        """
        try:
            pattern = f"{self.namespace}:*"
            keys = self.redis.keys(pattern)

            if keys:
                result = self.redis.delete(*keys)
                logger.info(f"Cleared {result} keys from namespace: {self.namespace}")
                return result

            return 0

        except Exception as e:
            logger.error(f"Cache clear error for namespace {self.namespace}: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        try:
            full_key = self._make_key(key)
            return bool(self.redis.exists(full_key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    def ttl(self, key: str) -> int:
        """
        Get remaining TTL for key

        Args:
            key: Cache key

        Returns:
            TTL in seconds, -2 if key doesn't exist, -1 if no expiry
        """
        try:
            full_key = self._make_key(key)
            return self.redis.ttl(full_key)
        except Exception as e:
            logger.error(f"Cache TTL error for key {key}: {e}")
            return -2


class EmbeddingCache(CacheService):
    """
    Specialized cache for embeddings with content-based keys
    """

    def __init__(self):
        super().__init__(namespace="embeddings")

    def make_content_key(self, content: str) -> str:
        """
        Create cache key based on content hash

        Args:
            content: Text content to hash

        Returns:
            Hash-based cache key
        """
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return content_hash

    def get_embedding(self, content: str) -> Optional[list[float]]:
        """
        Get cached embedding for content

        Args:
            content: Text content

        Returns:
            Embedding vector or None
        """
        key = self.make_content_key(content)
        return self.get(key)

    def set_embedding(
        self,
        content: str,
        embedding: list[float],
        ttl_days: int = 30,
    ) -> bool:
        """
        Cache embedding for content

        Args:
            content: Text content
            embedding: Embedding vector
            ttl_days: Time to live in days

        Returns:
            True if successful
        """
        key = self.make_content_key(content)
        ttl_seconds = ttl_days * 24 * 3600
        return self.set(key, embedding, ttl_seconds)


class ResearchCache(CacheService):
    """
    Specialized cache for company research
    """

    def __init__(self):
        super().__init__(namespace="research")

    def get_company_research(self, company_domain: str) -> Optional[dict]:
        """
        Get cached research for company

        Args:
            company_domain: Company domain (e.g., stripe.com)

        Returns:
            Research data or None
        """
        return self.get(company_domain)

    def set_company_research(
        self,
        company_domain: str,
        research_data: dict,
        ttl_hours: int = 24,
    ) -> bool:
        """
        Cache company research

        Args:
            company_domain: Company domain
            research_data: Research data
            ttl_hours: Time to live in hours

        Returns:
            True if successful
        """
        ttl_seconds = ttl_hours * 3600
        return self.set(company_domain, research_data, ttl_seconds)


class ScoreCache(CacheService):
    """
    Specialized cache for scoring results
    """

    def __init__(self):
        super().__init__(namespace="scores")

    def make_score_key(self, resume_id: str, job_id: str) -> str:
        """
        Create cache key for score

        Args:
            resume_id: Resume ID
            job_id: Job ID

        Returns:
            Cache key
        """
        return f"{resume_id}:{job_id}"

    def get_score(self, resume_id: str, job_id: str) -> Optional[dict]:
        """
        Get cached score

        Args:
            resume_id: Resume ID
            job_id: Job ID

        Returns:
            Score data or None
        """
        key = self.make_score_key(resume_id, job_id)
        return self.get(key)

    def set_score(
        self,
        resume_id: str,
        job_id: str,
        score_data: dict,
        ttl_hours: int = 1,
    ) -> bool:
        """
        Cache score data

        Args:
            resume_id: Resume ID
            job_id: Job ID
            score_data: Score data
            ttl_hours: Time to live in hours

        Returns:
            True if successful
        """
        key = self.make_score_key(resume_id, job_id)
        ttl_seconds = ttl_hours * 3600
        return self.set(key, score_data, ttl_seconds)


# Export cache instances
embedding_cache = EmbeddingCache()
research_cache = ResearchCache()
score_cache = ScoreCache()

__all__ = [
    "CacheService",
    "EmbeddingCache",
    "ResearchCache",
    "ScoreCache",
    "embedding_cache",
    "research_cache",
    "score_cache",
]
