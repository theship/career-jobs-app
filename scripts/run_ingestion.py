#!/usr/bin/env python3
"""
Job Ingestion Script
Run job ingestion from command line or as scheduled task
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.orchestrator import JobIngestionOrchestrator  # noqa: E402, F401


def setup_logging(verbose: bool = False):
    """Configure logging for the script"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/ingestion.log", mode="a"),
        ],
    )
    return logging.getLogger(__name__)


async def main():
    """Main entry point for the ingestion script"""
    parser = argparse.ArgumentParser(description="Run job ingestion from ATS sources")
    parser.add_argument(
        "--sources",
        nargs="+",
        help="Specific ATS sources to ingest from (e.g., greenhouse lever)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of jobs to ingest per source",
    )
    parser.add_argument(
        "--no-normalize", action="store_true", help="Skip normalization step"
    )
    parser.add_argument(
        "--no-store", action="store_true", help="Skip storing to database (dry run)"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Run cleanup after ingestion (dedup, expire old jobs)",
    )
    parser.add_argument(
        "--update-embeddings",
        action="store_true",
        help="Update embeddings for jobs without them",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)

    # Setup logging
    logger = setup_logging(args.verbose)
    logger.info("Starting job ingestion script")

    try:
        # Create orchestrator
        orchestrator = JobIngestionOrchestrator()

        # Run ingestion
        if args.sources:
            # Ingest from specific sources
            logger.info(f"Ingesting from specific sources: {args.sources}")
            results = {}
            for source in args.sources:
                if source in orchestrator.connectors:
                    jobs = await orchestrator.ingest_from_source(
                        orchestrator.connectors[source],
                        source,
                        limit=args.limit,
                        normalize=not args.no_normalize,
                        store=not args.no_store,
                    )
                    results[source] = jobs
                    logger.info(f"Ingested {len(jobs)} jobs from {source}")
                else:
                    logger.warning(f"Unknown source: {source}")
        else:
            # Ingest from all configured sources
            logger.info("Ingesting from all configured sources")
            results = await orchestrator.ingest_all_sources(
                limit_per_source=args.limit,
                normalize=not args.no_normalize,
                store=not args.no_store,
            )

        # Log summary
        total_jobs = sum(len(jobs) for jobs in results.values())
        logger.info(f"Total jobs ingested: {total_jobs} from {len(results)} sources")

        # Optional cleanup
        if args.cleanup and not args.no_store:
            logger.info("Running cleanup tasks...")
            duplicates_removed = await orchestrator.deduplicate_jobs()
            expired_cleaned = await orchestrator.cleanup_expired_jobs()
            logger.info(
                f"Cleanup complete: {duplicates_removed} duplicates removed, "
                f"{expired_cleaned} expired jobs cleaned"
            )

        # Optional embedding update
        if args.update_embeddings and not args.no_store:
            logger.info("Updating embeddings...")
            updated = await orchestrator.update_job_embeddings(batch_size=20)
            logger.info(f"Updated {updated} job embeddings")

        logger.info("Ingestion script completed successfully")
        return 0

    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
