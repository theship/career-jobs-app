"""
Company Management Service
Handles CRUD operations and business logic for target companies
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from supabase import Client

logger = logging.getLogger(__name__)


class CompanyManager:
    """Service for managing target companies and ingestion scheduling"""
    
    def __init__(self, supabase_client: Client):
        """
        Initialize company manager
        
        Args:
            supabase_client: Supabase client with service role access
        """
        self.supabase = supabase_client
        self.auto_disable_threshold = 5  # Disable after 5 consecutive failures
    
    async def get_all_companies(
        self, 
        active_only: bool = True,
        ats_system: Optional[str] = None
    ) -> List[Dict]:
        """
        Get all target companies
        
        Args:
            active_only: Only return active companies
            ats_system: Filter by specific ATS system
            
        Returns:
            List of company records
        """
        try:
            query = self.supabase.table("target_companies").select("*")
            
            if active_only:
                query = query.eq("active", True)
            
            if ats_system:
                query = query.eq("ats_system", ats_system)
            
            result = query.order("priority", desc=False).order("display_name").execute()
            return result.data
        except Exception as e:
            logger.error(f"Failed to fetch companies: {e}")
            return []
    
    async def get_companies_for_ingestion(
        self, 
        limit: int = 50,
        ats_system: Optional[str] = None
    ) -> List[Dict]:
        """
        Get companies that are due for ingestion
        
        Args:
            limit: Maximum number of companies to return
            ats_system: Filter by specific ATS system
            
        Returns:
            List of companies ready for ingestion
        """
        try:
            # Get active companies
            query = self.supabase.table("target_companies").select("*").eq("active", True)
            
            if ats_system:
                query = query.eq("ats_system", ats_system)
            
            # Order by priority and last fetch time
            result = query.order("priority", desc=False).order("last_successful_fetch", desc=False, nullsfirst=True).limit(limit).execute()
            
            companies = result.data
            
            # Filter companies based on check frequency
            due_companies = []
            now = datetime.now(timezone.utc)
            
            for company in companies:
                # If never fetched, include it
                if not company.get("last_successful_fetch"):
                    due_companies.append(company)
                    continue
                
                # Check if enough time has passed since last fetch
                last_fetch = datetime.fromisoformat(company["last_successful_fetch"].replace("Z", "+00:00"))
                check_days = company.get("check_frequency_days", 1)
                next_check = last_fetch + timedelta(days=check_days)
                
                if now >= next_check:
                    due_companies.append(company)
            
            return due_companies[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get companies for ingestion: {e}")
            return []
    
    async def add_company(
        self,
        ats_system: str,
        company_id: str,
        display_name: str,
        industry: Optional[str] = None,
        priority: int = 2,
        check_frequency_days: int = 1,
        metadata: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Add a new target company
        
        Args:
            ats_system: ATS system (lever, greenhouse, ashby)
            company_id: Company identifier for the ATS
            display_name: Display name for the company
            industry: Industry category
            priority: Priority level (1=high, 2=medium, 3=low)
            check_frequency_days: How often to check for new jobs
            metadata: Additional configuration
            
        Returns:
            Created company record or None if failed
        """
        try:
            data = {
                "ats_system": ats_system,
                "company_id": company_id,
                "display_name": display_name,
                "industry": industry,
                "priority": priority,
                "check_frequency_days": check_frequency_days,
                "metadata": metadata or {},
                "active": True
            }
            
            result = self.supabase.table("target_companies").insert(data).execute()
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.error(f"Failed to add company: {e}")
            return None
    
    async def update_company(
        self,
        company_uuid: str,
        **updates
    ) -> Optional[Dict]:
        """
        Update a target company
        
        Args:
            company_uuid: Company UUID
            **updates: Fields to update
            
        Returns:
            Updated company record or None if failed
        """
        try:
            # Add updated_at timestamp
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            result = self.supabase.table("target_companies").update(updates).eq("id", company_uuid).execute()
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.error(f"Failed to update company {company_uuid}: {e}")
            return None
    
    async def record_fetch_attempt(
        self,
        company_uuid: str,
        success: bool,
        jobs_fetched: int = 0,
        error_details: Optional[str] = None
    ) -> None:
        """
        Record a fetch attempt for a company
        
        Args:
            company_uuid: Company UUID
            success: Whether the fetch was successful
            jobs_fetched: Number of jobs fetched
            error_details: Error details if failed
        """
        try:
            # Get current company data
            result = self.supabase.table("target_companies").select("*").eq("id", company_uuid).execute()
            
            if not result.data:
                logger.error(f"Company {company_uuid} not found")
                return
            
            company = result.data[0]
            consecutive_failures = company.get("consecutive_failures", 0)
            
            updates = {
                "last_fetch_attempt": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            if success:
                updates["last_successful_fetch"] = datetime.now(timezone.utc).isoformat()
                updates["consecutive_failures"] = 0
                updates["error_details"] = None
            else:
                consecutive_failures += 1
                updates["consecutive_failures"] = consecutive_failures
                updates["error_details"] = error_details
                
                # Auto-disable if too many failures
                if consecutive_failures >= self.auto_disable_threshold:
                    updates["active"] = False
                    logger.warning(
                        f"Auto-disabling company {company['display_name']} after {consecutive_failures} failures"
                    )
            
            # Update company record
            self.supabase.table("target_companies").update(updates).eq("id", company_uuid).execute()
            
        except Exception as e:
            logger.error(f"Failed to record fetch attempt for {company_uuid}: {e}")
    
    async def record_ingestion_history(
        self,
        company_uuid: str,
        started_at: datetime,
        completed_at: Optional[datetime] = None,
        jobs_fetched: int = 0,
        jobs_created: int = 0,
        jobs_updated: int = 0,
        embeddings_generated: int = 0,
        status: str = "running",
        error_details: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[str]:
        """
        Record ingestion history entry
        
        Args:
            company_uuid: Company UUID
            started_at: When ingestion started
            completed_at: When ingestion completed
            jobs_fetched: Number of jobs fetched from ATS
            jobs_created: Number of new jobs created
            jobs_updated: Number of existing jobs updated
            embeddings_generated: Number of embeddings generated
            status: Status (running, success, partial, failed)
            error_details: Error details if failed
            metadata: Additional metadata
            
        Returns:
            History entry ID or None if failed
        """
        try:
            data = {
                "company_id": company_uuid,
                "started_at": started_at.isoformat(),
                "jobs_fetched": jobs_fetched,
                "jobs_created": jobs_created,
                "jobs_updated": jobs_updated,
                "embeddings_generated": embeddings_generated,
                "status": status,
                "error_details": error_details,
                "metadata": metadata or {}
            }
            
            if completed_at:
                data["completed_at"] = completed_at.isoformat()
                duration_ms = int((completed_at - started_at).total_seconds() * 1000)
                data["duration_ms"] = duration_ms
            
            result = self.supabase.table("ingestion_history").insert(data).execute()
            return result.data[0]["id"] if result.data else None
            
        except Exception as e:
            logger.error(f"Failed to record ingestion history: {e}")
            return None
    
    async def update_ingestion_history(
        self,
        history_id: str,
        **updates
    ) -> None:
        """
        Update an existing ingestion history entry
        
        Args:
            history_id: History entry ID
            **updates: Fields to update
        """
        try:
            self.supabase.table("ingestion_history").update(updates).eq("id", history_id).execute()
        except Exception as e:
            logger.error(f"Failed to update ingestion history {history_id}: {e}")
    
    async def get_company_stats(
        self,
        company_uuid: Optional[str] = None,
        days: int = 30
    ) -> Dict:
        """
        Get ingestion statistics for companies
        
        Args:
            company_uuid: Specific company UUID (optional)
            days: Number of days to look back
            
        Returns:
            Statistics dictionary
        """
        try:
            since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            
            query = self.supabase.table("ingestion_history").select("*").gte("started_at", since)
            
            if company_uuid:
                query = query.eq("company_id", company_uuid)
            
            result = query.execute()
            history = result.data
            
            # Calculate statistics
            stats = {
                "total_runs": len(history),
                "successful_runs": len([h for h in history if h["status"] == "success"]),
                "failed_runs": len([h for h in history if h["status"] == "failed"]),
                "total_jobs_fetched": sum(h.get("jobs_fetched", 0) for h in history),
                "total_jobs_created": sum(h.get("jobs_created", 0) for h in history),
                "total_jobs_updated": sum(h.get("jobs_updated", 0) for h in history),
                "total_embeddings": sum(h.get("embeddings_generated", 0) for h in history),
                "avg_duration_ms": 0,
                "success_rate": 0
            }
            
            if history:
                durations = [h["duration_ms"] for h in history if h.get("duration_ms")]
                if durations:
                    stats["avg_duration_ms"] = sum(durations) / len(durations)
                
                if stats["total_runs"] > 0:
                    stats["success_rate"] = stats["successful_runs"] / stats["total_runs"]
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get company stats: {e}")
            return {}
    
    async def delete_company(self, company_uuid: str) -> bool:
        """
        Delete a target company
        
        Args:
            company_uuid: Company UUID
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            self.supabase.table("target_companies").delete().eq("id", company_uuid).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete company {company_uuid}: {e}")
            return False