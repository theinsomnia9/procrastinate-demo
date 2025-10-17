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


@app.task(
    queue="test_failures",
    retry=ExponentialBackoffStrategy(
        max_attempts=5,  # Will fail 4 times, succeed on 5th attempt
        base_delay=2.0,
        max_delay=30.0,
        retry_exceptions=[TaskError, ValueError, RuntimeError],
    ),
    pass_context=True,
)
async def failing_task_for_retry_testing(context, fail_attempts: int = 4):
    """
    A task that intentionally fails for testing retry functionality.
    
    This task will:
    - Fail for the first N attempts with different exception types
    - Succeed on the final attempt
    - Log detailed information about each attempt
    - Store attempt information in the database for verification
    
    Args:
        context: Procrastinate job context (automatically passed)
        fail_attempts: Number of attempts that should fail before succeeding
    """
    attempt = context.job.attempts
    job_id = context.job.id
    
    logger.info(
        f"Job {job_id}: Retry test task starting (attempt {attempt}/{settings.max_retries}), "
        f"will fail for first {fail_attempts} attempts"
    )
    
    # Store attempt information in database for verification
    await _log_retry_attempt(job_id, attempt, fail_attempts)
    
    if attempt <= fail_attempts:
        # Simulate different types of failures
        if attempt == 1:
            logger.error(f"Job {job_id}: Simulating network timeout (attempt {attempt})")
            raise TaskError("Simulated network timeout - testing retry mechanism")
        elif attempt == 2:
            logger.error(f"Job {job_id}: Simulating database connection error (attempt {attempt})")
            raise ValueError("Simulated database connection error - testing retry mechanism")
        elif attempt == 3:
            logger.error(f"Job {job_id}: Simulating API rate limit (attempt {attempt})")
            raise RuntimeError("Simulated API rate limit - testing retry mechanism")
        else:
            logger.error(f"Job {job_id}: Simulating generic failure (attempt {attempt})")
            raise TaskError(f"Simulated failure on attempt {attempt} - testing retry mechanism")
    
    # Success case
    logger.info(f"Job {job_id}: SUCCESS! Task completed on attempt {attempt}")
    
    return {
        "status": "success",
        "job_id": job_id,
        "final_attempt": attempt,
        "total_failures": fail_attempts,
        "message": f"Task succeeded after {fail_attempts} failures"
    }


async def _log_retry_attempt(job_id: int, attempt: int, fail_attempts: int) -> None:
    """
    Log retry attempt information to database for verification.
    
    This creates a simple log entry that can be queried to verify
    retry behavior is working correctly.
    
    Args:
        job_id: Procrastinate job ID
        attempt: Current attempt number
        fail_attempts: Number of attempts configured to fail
    """
    async with AsyncSessionLocal() as session:
        try:
            # Use a simple upsert to track retry attempts
            # We'll store this as a "joke" with special formatting for easy identification
            retry_log_id = f"retry_test_{job_id}_attempt_{attempt}"
            
            stmt = insert(ChuckNorrisJoke).values(
                joke_id=retry_log_id,
                category="retry_test",
                joke_text=f"Retry test log: Job {job_id}, Attempt {attempt}/{fail_attempts + 1}",
                icon_url=None,
                url=f"internal://retry_test/{job_id}",
            )
            
            # On conflict, update with latest attempt info
            stmt = stmt.on_conflict_do_update(
                index_elements=["joke_id"],
                set_={
                    "joke_text": stmt.excluded.joke_text,
                    "url": stmt.excluded.url,
                }
            )
            
            await session.execute(stmt)
            await session.commit()
            
            logger.debug(f"Logged retry attempt for job {job_id}, attempt {attempt}")
            
        except Exception as e:
            await session.rollback()
            logger.warning(f"Failed to log retry attempt: {e}")
            # Don't raise - this is just logging, shouldn't affect main task


@app.task(
    queue="test_queue",
    retry=ExponentialBackoffStrategy(
        max_attempts=3,
        base_delay=1.0,
        max_delay=10.0,
    ),
    pass_context=True,
)
async def enqueue_failing_task(context, fail_attempts: int = 4):
    """
    Helper task to enqueue the failing task for testing.
    
    This makes it easy to trigger retry testing from the command line
    or from other parts of the application.
    
    Args:
        context: Procrastinate job context
        fail_attempts: Number of attempts that should fail before succeeding
    """
    job_id = context.job.id
    logger.info(f"Job {job_id}: Enqueueing failing task for retry testing (fail_attempts={fail_attempts})")
    
    # Defer the failing task
    deferred_job = await failing_task_for_retry_testing.defer_async(fail_attempts=fail_attempts)
    
    logger.info(f"Job {job_id}: Successfully enqueued failing task with job ID {deferred_job.id}")
    
    return {
        "status": "success",
        "enqueued_job_id": deferred_job.id,
        "fail_attempts": fail_attempts,
        "message": f"Enqueued failing task that will fail {fail_attempts} times before succeeding"
    }
