#!/usr/bin/env python3
"""
Migrate Companies from CSV to Database
One-time script to populate target_companies table from CSV
"""

import asyncio
import csv
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.utils.config import get_settings
from api.services.company_manager import CompanyManager
from supabase import create_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def load_csv_companies(csv_path: str = "config/target_companies.csv"):
    """Load companies from CSV file"""
    companies = []
    
    csv_file = Path(csv_path)
    if not csv_file.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return companies
    
    with open(csv_file, "r") as f:
        # Skip comment lines
        lines = [line for line in f if not line.startswith('#')]
        reader = csv.DictReader(lines)
        for row in reader:
            if row.get('ats_system'):  # Only add valid rows
                companies.append(row)
    
    logger.info(f"Loaded {len(companies)} companies from CSV")
    return companies


async def migrate_companies():
    """Migrate companies from CSV to database"""
    
    # Initialize Supabase client
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    company_manager = CompanyManager(supabase)
    
    # Load companies from CSV
    csv_companies = await load_csv_companies()
    
    if not csv_companies:
        logger.error("No companies to migrate")
        return
    
    # Check existing companies in database
    existing = await company_manager.get_all_companies(active_only=False)
    existing_keys = set()
    for c in existing:
        if 'ats_system' in c and 'company_id' in c:
            existing_keys.add(f"{c['ats_system']}_{c['company_id']}")
    
    logger.info(f"Found {len(existing)} existing companies in database")
    
    # Process each company from CSV
    created = 0
    updated = 0
    skipped = 0
    
    for company in csv_companies:
        key = f"{company['ats_system']}_{company['company_id']}"
        
        # Skip if already exists
        if key in existing_keys:
            logger.debug(f"Skipping existing company: {key}")
            skipped += 1
            continue
        
        # Create new company
        try:
            # Parse priority (default to 2 if not specified)
            priority = 2
            if company.get("priority"):
                try:
                    priority = int(company["priority"])
                except:
                    priority = 2
            
            # Determine if active
            active = company.get("active", "true").lower() == "true"
            
            result = await company_manager.add_company(
                ats_system=company["ats_system"],
                company_id=company["company_id"],
                display_name=company["display_name"],
                industry=company.get("industry"),
                priority=priority,
                check_frequency_days=1,
                metadata={}
            )
            
            if result:
                created += 1
                logger.info(f"Created company: {company['display_name']}")
            else:
                logger.error(f"Failed to create company: {company['display_name']}")
                
        except Exception as e:
            logger.error(f"Error creating company {company['display_name']}: {e}")
    
    # Add additional companies not in CSV
    additional_companies = [
        # More Lever companies
        {"ats_system": "lever", "company_id": "duolingo", "display_name": "Duolingo", "industry": "Education"},
        {"ats_system": "lever", "company_id": "instacart", "display_name": "Instacart", "industry": "Delivery"},
        {"ats_system": "lever", "company_id": "squarespace", "display_name": "Squarespace", "industry": "Web Platform"},
        {"ats_system": "lever", "company_id": "affirm", "display_name": "Affirm", "industry": "Fintech"},
        {"ats_system": "lever", "company_id": "robinhood", "display_name": "Robinhood", "industry": "Fintech"},
        {"ats_system": "lever", "company_id": "chime", "display_name": "Chime", "industry": "Fintech"},
        
        # More Greenhouse companies  
        {"ats_system": "greenhouse", "company_id": "github", "display_name": "GitHub", "industry": "Developer Tools"},
        {"ats_system": "greenhouse", "company_id": "gitlab", "display_name": "GitLab", "industry": "DevOps"},
        {"ats_system": "greenhouse", "company_id": "hashicorp", "display_name": "HashiCorp", "industry": "Infrastructure"},
        {"ats_system": "greenhouse", "company_id": "mongodb", "display_name": "MongoDB", "industry": "Database"},
        {"ats_system": "greenhouse", "company_id": "elastic", "display_name": "Elastic", "industry": "Search/Analytics"},
        {"ats_system": "greenhouse", "company_id": "confluent", "display_name": "Confluent", "industry": "Data Streaming"},
        
        # Ashby companies
        {"ats_system": "ashby", "company_id": "notion", "display_name": "Notion", "industry": "Productivity"},
        {"ats_system": "ashby", "company_id": "linear", "display_name": "Linear", "industry": "Project Management"},
        {"ats_system": "ashby", "company_id": "retool", "display_name": "Retool", "industry": "Developer Tools"},
        {"ats_system": "ashby", "company_id": "vercel", "display_name": "Vercel", "industry": "Cloud Platform"},
        {"ats_system": "ashby", "company_id": "anthropic", "display_name": "Anthropic", "industry": "AI/ML"},
        {"ats_system": "ashby", "company_id": "openai", "display_name": "OpenAI", "industry": "AI/ML"},
        {"ats_system": "ashby", "company_id": "ramp", "display_name": "Ramp", "industry": "Fintech"},
        {"ats_system": "ashby", "company_id": "brex", "display_name": "Brex", "industry": "Fintech"},
        {"ats_system": "ashby", "company_id": "rippling", "display_name": "Rippling", "industry": "HR Tech"},
        {"ats_system": "ashby", "company_id": "canva", "display_name": "Canva", "industry": "Design Tools"},
        {"ats_system": "ashby", "company_id": "mercury", "display_name": "Mercury", "industry": "Banking"},
        {"ats_system": "ashby", "company_id": "airtable", "display_name": "Airtable", "industry": "Productivity"},
    ]
    
    logger.info(f"Adding {len(additional_companies)} additional companies...")
    
    for company in additional_companies:
        key = f"{company['ats_system']}_{company['company_id']}"
        
        # Skip if already exists
        if key in existing_keys:
            logger.debug(f"Skipping existing company: {key}")
            skipped += 1
            continue
        
        try:
            result = await company_manager.add_company(
                ats_system=company["ats_system"],
                company_id=company["company_id"],
                display_name=company["display_name"],
                industry=company.get("industry"),
                priority=1 if company["industry"] in ["AI/ML", "Fintech", "Developer Tools"] else 2,
                check_frequency_days=1,
                metadata={}
            )
            
            if result:
                created += 1
                logger.info(f"Created company: {company['display_name']}")
                
        except Exception as e:
            logger.error(f"Error creating company {company['display_name']}: {e}")
    
    # Summary
    logger.info(f"""
Migration complete:
- Created: {created} companies
- Updated: {updated} companies  
- Skipped: {skipped} companies (already exist)
- Total in database: {len(existing) + created}
""")
    
    # Show some companies for verification
    final_companies = await company_manager.get_all_companies(active_only=True)
    
    logger.info("Sample of companies in database:")
    for company in final_companies[:10]:
        logger.info(f"  - {company['ats_system']}: {company['display_name']} (priority={company['priority']})")
    
    if len(final_companies) > 10:
        logger.info(f"  ... and {len(final_companies) - 10} more")


if __name__ == "__main__":
    asyncio.run(migrate_companies())