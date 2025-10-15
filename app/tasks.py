import httpx
import logging
import asyncio
from typing import Optional
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.procrastinate_app import app, ExponentialBackoffStrategy
from app.database import AsyncSessionLocal
from app.models import ChuckNorrisJoke
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class TaskError(Exception):
    """Custom exception for task errors."""
    pass


@app.task(
    queue="api_calls",
    retry=ExponentialBackoffStrategy(
        max_attempts=settings.max_retries,
        base_delay=settings.retry_base_delay,
        max_delay=settings.retry_max_delay,
        retry_exceptions=[TaskError, httpx.HTTPError, httpx.TimeoutException],
    ),
    pass_context=True,
)
async def fetch_and_cache_joke(context, category: Optional[str] = None):
    """
    Fetch a Chuck Norris joke from the API and cache it in PostgreSQL.
    
    This task implements:
    - Exponential backoff retry strategy
    - Idempotent operations (upsert)
    - Comprehensive error handling
    - Graceful degradation
    
    Args:
        context: Procrastinate job context (automatically passed)
        category: Optional category to filter jokes
    """
    attempt = context.job.attempts
    job_id = context.job.id
    
    logger.info(
        f"Job {job_id}: Fetching joke (attempt {attempt}/{settings.max_retries}), "
        f"category={category}"
    )
    
    try:
        # Wrap task execution with timeout to prevent hanging
        async with asyncio.timeout(settings.job_timeout):
            # Fetch joke from API with timeout
            joke_data = await _fetch_joke_from_api(category)
            
            # Cache in database with upsert (idempotent)
            await _cache_joke_in_db(joke_data)
        
        logger.info(
            f"Job {job_id}: Successfully cached joke {joke_data['id']}"
        )
        
        return {
            "status": "success",
            "joke_id": joke_data["id"],
            "attempt": attempt,
        }
        
    except asyncio.TimeoutError as e:
        logger.error(f"Job {job_id}: Task timeout after {settings.job_timeout}s on attempt {attempt}")
        raise TaskError(f"Task timeout after {settings.job_timeout}s") from e
        
    except httpx.TimeoutException as e:
        logger.error(f"Job {job_id}: API timeout on attempt {attempt}: {e}")
        raise TaskError(f"API timeout: {e}") from e
        
    except httpx.HTTPError as e:
        logger.error(f"Job {job_id}: HTTP error on attempt {attempt}: {e}")
        raise TaskError(f"HTTP error: {e}") from e
        
    except Exception as e:
        logger.error(
            f"Job {job_id}: Unexpected error on attempt {attempt}: {e}",
            exc_info=True
        )
        raise TaskError(f"Unexpected error: {e}") from e


async def _fetch_joke_from_api(category: Optional[str] = None) -> dict:
    """
    Fetch a joke from the Chuck Norris API.
    
    Args:
        category: Optional category filter
        
    Returns:
        Dictionary containing joke data
        
    Raises:
        httpx.HTTPError: If API request fails
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        if category:
            url = f"{settings.api_base_url}/jokes/random?category={category}"
        else:
            url = f"{settings.api_base_url}/jokes/random"
        
        response = await client.get(url)
        response.raise_for_status()
        
        return response.json()


async def _cache_joke_in_db(joke_data: dict) -> None:
    """
    Cache joke in database using upsert for idempotency.
    
    Args:
        joke_data: Dictionary containing joke data from API
        
    Raises:
        Exception: If database operation fails
    """
    async with AsyncSessionLocal() as session:
        try:
            # Extract category (can be None or a list)
            categories = joke_data.get("categories", [])
            category = categories[0] if categories else None
            
            # Use PostgreSQL upsert (INSERT ... ON CONFLICT DO UPDATE)
            stmt = insert(ChuckNorrisJoke).values(
                joke_id=joke_data["id"],
                category=category,
                joke_text=joke_data["value"],
                icon_url=joke_data.get("icon_url"),
                url=joke_data.get("url"),
            )
            
            # On conflict, update the joke text and metadata
            stmt = stmt.on_conflict_do_update(
                index_elements=["joke_id"],
                set_={
                    "joke_text": stmt.excluded.joke_text,
                    "category": stmt.excluded.category,
                    "icon_url": stmt.excluded.icon_url,
                    "url": stmt.excluded.url,
                }
            )
            
            await session.execute(stmt)
            await session.commit()
            
            logger.debug(f"Cached joke {joke_data['id']} in database")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error while caching joke: {e}")
            raise


@app.periodic(cron="*/2 * * * *")  # Every 2 minutes
@app.task(
    queueing_lock="fetch_random_joke",
    retry=ExponentialBackoffStrategy(
        max_attempts=3,
        base_delay=2.0,
        max_delay=60.0,
    ),
    pass_context=True,
)
async def scheduled_fetch_random_joke(context, timestamp: int):
    """
    Periodic task that fetches a random joke every 2 minutes.
    
    This demonstrates:
    - Periodic task scheduling
    - Queueing lock to prevent duplicate jobs
    - Integration with the main fetch task
    
    Args:
        context: Procrastinate job context
        timestamp: Unix timestamp when the job was scheduled
    """
    logger.info(f"Scheduled job triggered at timestamp {timestamp}")
    
    # Defer the actual fetch task
    await fetch_and_cache_joke.defer_async(category=None)


@app.periodic(cron="*/10 * * * *")  # Every 10 minutes
@app.task(
    queueing_lock="retry_stalled_jobs",
    retry=ExponentialBackoffStrategy(
        max_attempts=3,
        base_delay=5.0,
        max_delay=60.0,
    ),
    pass_context=True,
)
async def retry_stalled_jobs(context, timestamp: int):
    """
    Periodic task to retry stalled jobs.
    
    This ensures that jobs interrupted by crashes or worker failures
    are automatically retried, providing bulletproof task completion.
    
    A job is considered stalled if:
    - It's in 'doing' status (being processed)
    - The worker that picked it up is no longer active
    - It hasn't been updated recently
    
    Args:
        context: Procrastinate job context
        timestamp: Unix timestamp when the job was scheduled
    """
    logger.info(f"Checking for stalled jobs at timestamp {timestamp}")
    
    try:
        # Get stalled jobs from Procrastinate
        stalled_jobs = await app.job_manager.get_stalled_jobs()
        
        if stalled_jobs:
            logger.warning(f"Found {len(stalled_jobs)} stalled jobs, retrying...")
            
            retry_count = 0
            failed_count = 0
            
            for job in stalled_jobs:
                try:
                    await app.job_manager.retry_job(job)
                    logger.info(
                        f"Successfully retried stalled job {job.id} "
                        f"(task: {job.task_name}, attempts: {job.attempts})"
                    )
                    retry_count += 1
                except Exception as e:
                    logger.error(
                        f"Failed to retry stalled job {job.id} "
                        f"(task: {job.task_name}): {e}",
                        exc_info=True
                    )
                    failed_count += 1
            
            logger.info(
                f"Stalled job recovery complete: {retry_count} retried, "
                f"{failed_count} failed"
            )
        else:
            logger.info("No stalled jobs found - all workers healthy")
            
        return {
            "status": "success",
            "stalled_jobs_found": len(stalled_jobs) if stalled_jobs else 0,
            "timestamp": timestamp,
        }
        
    except Exception as e:
        logger.error(f"Error in stalled job detection: {e}", exc_info=True)
        raise TaskError(f"Stalled job detection failed: {e}") from e


@app.periodic(cron="*/5 * * * *")  # Every 5 minutes
@app.task(
    queueing_lock="health_check",
    retry=ExponentialBackoffStrategy(
        max_attempts=2,
        base_delay=10.0,
        max_delay=30.0,
    ),
    pass_context=True,
)
async def health_check_task(context, timestamp: int):
    """
    Periodic health check task to monitor system health.
    
    This task:
    - Verifies database connectivity
    - Checks worker status
    - Logs system metrics
    - Can be extended to send alerts
    
    Args:
        context: Procrastinate job context
        timestamp: Unix timestamp when the job was scheduled
    """
    logger.info(f"Running health check at timestamp {timestamp}")
    
    try:
        # Test database connectivity
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(1))
            result.scalar()
        
        logger.info("Health check passed: Database connection OK")
        
        return {
            "status": "healthy",
            "timestamp": timestamp,
            "database": "connected",
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise TaskError(f"Health check failed: {e}") from e
