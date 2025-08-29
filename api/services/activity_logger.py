"""
Activity logging service for tracking user actions and system events
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from ..utils.database import get_supabase_client

logger = logging.getLogger(__name__)


class ActivityLogger:
    """Service for logging user activities and system events to database"""

    def __init__(self):
        self.supabase = get_supabase_client()
        self._start_times = {}  # Track action start times

    async def log_action_start(
        self,
        user_id: str,
        action_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Log the start of an action

        Args:
            user_id: User performing the action
            action_type: Type of action (resume_upload, skills_upload, scoring_run, csv_export)
            metadata: Additional context data

        Returns:
            log_id for tracking the action
        """
        # TEMPORARILY DISABLED - Table not yet created
        logger.info(
            f"[ACTIVITY] Action started: {action_type} for user {user_id} - {json.dumps(metadata or {})}"
        )
        return f"temp_{action_type}_{time.time()}"  # Return temp ID

        try:
            start_time = datetime.utcnow()

            # Store start time for duration calculation
            log_data = {
                "user_id": user_id,
                "action_type": action_type,
                "action_status": "started",
                "metadata": metadata or {},
                "started_at": start_time.isoformat(),
            }

            # Log to console for debugging
            logger.info(
                f"Action started: {action_type} for user {user_id} - {json.dumps(metadata or {})}"
            )

            # Insert into database
            response = self.supabase.table("activity_log").insert(log_data).execute()

            if response.data:
                log_id = str(response.data[0]["log_id"])
                self._start_times[log_id] = time.time()
                return log_id

        except Exception as e:
            logger.error(f"Failed to log action start: {e}")
            return ""

    async def update_action_progress(
        self,
        log_id: str,
        status: str = "in_progress",
        progress_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Update progress of an ongoing action

        Args:
            log_id: ID of the action log entry
            status: Current status
            progress_data: Progress information to merge with metadata
        """
        # TEMPORARILY DISABLED - Table not yet created
        logger.info(
            f"[ACTIVITY] Progress: {log_id} - {json.dumps(progress_data or {})}"
        )
        return

        try:
            if progress_data:
                # Get existing metadata
                response = (
                    self.supabase.table("activity_log")
                    .select("metadata")
                    .eq("log_id", log_id)
                    .execute()
                )

                if response.data:
                    existing_metadata = response.data[0].get("metadata", {})
                    # Merge progress data
                    updated_metadata = {**existing_metadata, **progress_data}

                    # Update the log entry
                    self.supabase.table("activity_log").update(
                        {
                            "action_status": status,
                            "metadata": updated_metadata,
                        }
                    ).eq("log_id", log_id).execute()

                    # Log progress for debugging
                    logger.info(
                        f"Action progress: {log_id} - {json.dumps(progress_data)}"
                    )

        except Exception as e:
            logger.error(f"Failed to update action progress: {e}")

    async def log_action_complete(
        self,
        log_id: str,
        success: bool = True,
        result_data: Optional[Dict[str, Any]] = None,
        error_details: Optional[str] = None,
    ):
        """
        Log the completion of an action

        Args:
            log_id: ID of the action log entry
            success: Whether the action succeeded
            result_data: Final result data to merge with metadata
            error_details: Error message if action failed
        """
        # TEMPORARILY DISABLED - Table not yet created
        status_msg = "succeeded" if success else "failed"
        logger.info(
            f"[ACTIVITY] Action {status_msg}: {log_id} - {json.dumps(result_data or {})}"
        )
        if error_details:
            logger.error(f"[ACTIVITY] Error: {log_id} - {error_details}")
        return

        try:
            # Calculate duration
            duration_ms = None
            if log_id in self._start_times:
                duration_ms = int((time.time() - self._start_times[log_id]) * 1000)
                del self._start_times[log_id]

            # Get existing metadata
            response = (
                self.supabase.table("activity_log")
                .select("metadata, action_type, user_id")
                .eq("log_id", log_id)
                .execute()
            )

            if response.data:
                log_entry = response.data[0]
                existing_metadata = log_entry.get("metadata", {})

                # Merge result data
                if result_data:
                    updated_metadata = {**existing_metadata, **result_data}
                else:
                    updated_metadata = existing_metadata

                # Update the log entry
                update_data = {
                    "action_status": "completed" if success else "failed",
                    "metadata": updated_metadata,
                    "completed_at": datetime.utcnow().isoformat(),
                    "duration_ms": duration_ms,
                }

                if error_details:
                    update_data["error_details"] = error_details

                self.supabase.table("activity_log").update(update_data).eq(
                    "log_id", log_id
                ).execute()

                # Log completion for debugging
                status_msg = "succeeded" if success else "failed"
                logger.info(
                    f"Action {status_msg}: {log_entry['action_type']} for user {log_entry['user_id']} "
                    f"- Duration: {duration_ms}ms - {json.dumps(result_data or {})}"
                )

                if error_details:
                    logger.error(f"Action error: {log_id} - {error_details}")

        except Exception as e:
            logger.error(f"Failed to log action completion: {e}")

    async def get_user_activity(
        self,
        user_id: str,
        limit: int = 20,
        action_type: Optional[str] = None,
    ) -> list:
        """
        Get recent activity for a user

        Args:
            user_id: User ID to get activity for
            limit: Maximum number of entries to return
            action_type: Filter by specific action type

        Returns:
            List of activity log entries
        """
        try:
            query = (
                self.supabase.table("activity_log")
                .select("*")
                .eq("user_id", user_id)
                .order("started_at", desc=True)
                .limit(limit)
            )

            if action_type:
                query = query.eq("action_type", action_type)

            response = query.execute()
            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Failed to get user activity: {e}")
            return []

    async def get_activity_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get summary statistics of user activity

        Args:
            user_id: User ID to get summary for

        Returns:
            Dictionary with activity statistics
        """
        try:
            # Get all user activities
            response = (
                self.supabase.table("activity_log")
                .select("action_type, action_status, duration_ms")
                .eq("user_id", user_id)
                .execute()
            )

            if not response.data:
                return {
                    "total_actions": 0,
                    "by_type": {},
                    "success_rate": 0,
                    "avg_duration_ms": 0,
                }

            activities = response.data

            # Calculate statistics
            by_type = {}
            total_duration = 0
            duration_count = 0
            success_count = 0

            for activity in activities:
                action_type = activity["action_type"]
                if action_type not in by_type:
                    by_type[action_type] = {"count": 0, "completed": 0, "failed": 0}

                by_type[action_type]["count"] += 1

                if activity["action_status"] == "completed":
                    by_type[action_type]["completed"] += 1
                    success_count += 1
                elif activity["action_status"] == "failed":
                    by_type[action_type]["failed"] += 1

                if activity.get("duration_ms"):
                    total_duration += activity["duration_ms"]
                    duration_count += 1

            return {
                "total_actions": len(activities),
                "by_type": by_type,
                "success_rate": (
                    (success_count / len(activities) * 100) if activities else 0
                ),
                "avg_duration_ms": (
                    (total_duration / duration_count) if duration_count > 0 else 0
                ),
            }

        except Exception as e:
            logger.error(f"Failed to get activity summary: {e}")
            return {
                "total_actions": 0,
                "by_type": {},
                "success_rate": 0,
                "avg_duration_ms": 0,
            }


# Global instance
activity_logger = ActivityLogger()
