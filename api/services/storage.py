"""Storage service for file management using Supabase Storage."""

import os
import uuid
from typing import Optional
from datetime import datetime
import logging
from supabase import create_client, Client
from fastapi import UploadFile

from ..utils.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Handle file storage operations with Supabase Storage."""

    def __init__(self):
        """Initialize Supabase storage client."""
        self.supabase: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,  # Use service role for storage operations
        )
        self.bucket_name = "resumes"
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Ensure the resumes bucket exists."""
        try:
            buckets = self.supabase.storage.list_buckets()
            bucket_names = [b.name for b in buckets]

            if self.bucket_name not in bucket_names:
                # Create the bucket with appropriate settings
                self.supabase.storage.create_bucket(
                    self.bucket_name,
                    options={
                        "public": False,  # Private bucket, requires auth
                        "fileSizeLimit": 10485760,  # 10MB limit
                        "allowedMimeTypes": [
                            "application/pdf",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            "text/plain",
                        ],
                    },
                )
                logger.info(f"Created storage bucket: {self.bucket_name}")
        except Exception as e:
            logger.warning(f"Could not ensure bucket exists: {e}")

    async def upload_resume(
        self, file: UploadFile, user_id: str, folder: Optional[str] = None
    ) -> str:
        """
        Upload a resume file to Supabase Storage.

        Args:
            file: The uploaded file
            user_id: The user's ID for organization
            folder: Optional subfolder name

        Returns:
            The storage path of the uploaded file
        """
        try:
            # Generate unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            file_extension = os.path.splitext(file.filename)[1]
            unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}{file_extension}"

            # Construct storage path
            if folder:
                storage_path = f"{user_id}/{folder}/{unique_filename}"
            else:
                storage_path = f"{user_id}/{unique_filename}"

            # Read file content
            content = await file.read()

            # Upload to Supabase Storage
            response = self.supabase.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=content,
                file_options={
                    "content-type": file.content_type or "application/octet-stream",
                    "cache-control": "3600",
                    "upsert": False,
                },
            )

            if response:
                logger.info(f"Successfully uploaded file to: {storage_path}")
                return storage_path
            else:
                raise Exception("Upload returned empty response")

        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            raise Exception(f"Failed to upload resume: {str(e)}")
        finally:
            # Reset file pointer
            await file.seek(0)

    async def download_resume(self, storage_path: str) -> bytes:
        """
        Download a resume file from Supabase Storage.

        Args:
            storage_path: The storage path of the file

        Returns:
            The file content as bytes
        """
        try:
            response = self.supabase.storage.from_(self.bucket_name).download(
                storage_path
            )

            if response:
                return response
            else:
                raise Exception("File not found")

        except Exception as e:
            logger.error(f"Failed to download file {storage_path}: {e}")
            raise Exception(f"Failed to download resume: {str(e)}")

    async def delete_resume(self, storage_path: str) -> bool:
        """
        Delete a resume file from Supabase Storage.

        Args:
            storage_path: The storage path of the file

        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.supabase.storage.from_(self.bucket_name).remove(
                [storage_path]
            )

            if response:
                logger.info(f"Successfully deleted file: {storage_path}")
                return True
            else:
                logger.warning(f"Could not delete file: {storage_path}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete file {storage_path}: {e}")
            return False

    async def get_signed_url(self, storage_path: str, expires_in: int = 3600) -> str:
        """
        Generate a signed URL for temporary file access.

        Args:
            storage_path: The storage path of the file
            expires_in: URL expiration time in seconds (default 1 hour)

        Returns:
            A signed URL for file access
        """
        try:
            response = self.supabase.storage.from_(self.bucket_name).create_signed_url(
                storage_path, expires_in=expires_in
            )

            if response and "signedURL" in response:
                return response["signedURL"]
            else:
                raise Exception("Could not generate signed URL")

        except Exception as e:
            logger.error(f"Failed to create signed URL for {storage_path}: {e}")
            raise Exception(f"Failed to create download link: {str(e)}")

    async def list_user_files(self, user_id: str, folder: Optional[str] = None) -> list:
        """
        List all files for a specific user.

        Args:
            user_id: The user's ID
            folder: Optional subfolder to list

        Returns:
            List of file metadata
        """
        try:
            if folder:
                path = f"{user_id}/{folder}"
            else:
                path = user_id

            response = self.supabase.storage.from_(self.bucket_name).list(
                path=path, options={"limit": 100, "offset": 0}
            )

            return response if response else []

        except Exception as e:
            logger.error(f"Failed to list files for user {user_id}: {e}")
            return []

    async def get_storage_usage(self, user_id: str) -> dict:
        """
        Get storage usage statistics for a user.

        Args:
            user_id: The user's ID

        Returns:
            Dictionary with storage usage information
        """
        try:
            files = await self.list_user_files(user_id)

            total_size = sum(file.get("metadata", {}).get("size", 0) for file in files)
            file_count = len(files)

            return {
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_count": file_count,
                "storage_limit_mb": 100,  # 100MB per user limit
                "usage_percentage": round((total_size / (100 * 1024 * 1024)) * 100, 2),
            }

        except Exception as e:
            logger.error(f"Failed to get storage usage for user {user_id}: {e}")
            return {
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "file_count": 0,
                "storage_limit_mb": 100,
                "usage_percentage": 0,
            }
