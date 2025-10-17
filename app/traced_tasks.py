"""
Procrastinate tasks with OpenTelemetry tracing integration.

This module demonstrates how to:
- Pass trace context through job extra arguments
- Track jobs from defer to completion
- Maintain distributed tracing across async job execution
"""

import asyncio
import logging
import httpx
from typing import Optional, Dict, Any
from sqlalchemy import select

from app.procrastinate_app import app, ExponentialBackoffStrategy
from app.database import AsyncSessionLocal
from app.models import ChuckNorrisJoke
from app.config import get_settings
from app.tracing import (
    extract_trace_context,
    trace_job_execution,
    trace_job_defer,
    get_tracer,
    get_current_trace_id,
    get_current_span_id
)

settings = get_settings()
logger = logging.getLogger(__name__)


@app.task(
    queue="traced_api_calls",
    retry=ExponentialBackoffStrategy(
        max_attempts=3,
        base_delay=2.0,
        max_delay=60.0,
    ),
    pass_context=True,
)
async def traced_fetch_joke(
    context, 
    category: Optional[str] = None,
    trace_context: Optional[Dict[str, str]] = None
):
    """
    Fetch a Chuck Norris joke with full OpenTelemetry tracing.
    
    This task demonstrates:
    - Extracting trace context from job arguments
    - Creating child spans for job execution
    - Tracing HTTP calls and database operations
    - Proper error handling with span status
    
    Args:
        context: Procrastinate job context
        category: Optional joke category
        trace_context: OpenTelemetry trace context from parent span
    """
    # Extract and set trace context if provided
    if trace_context:
        extract_trace_context(trace_context)
    
    job_id = context.job.id
    attempt = context.job.attempts
    
    # Create main job execution span
    with trace_job_execution(
        "fetch_joke",
        job_id=job_id,
        attempt=attempt,
        category=category or "random"
    ) as span:
        
        logger.info(
            f"Job {job_id}: Starting traced joke fetch (attempt {attempt}), "
            f"trace_id={get_current_trace_id()}, span_id={get_current_span_id()}"
        )
        
        try:
            # Fetch joke from API (automatically traced by HTTPXClientInstrumentor)
            joke_data = await _fetch_joke_from_api(category)
            span.set_attribute("joke.id", joke_data["id"])
            span.set_attribute("joke.category", joke_data.get("categories", ["uncategorized"])[0] if joke_data.get("categories") else "uncategorized")
            
            # Store in database (automatically traced by SQLAlchemyInstrumentor)
            await _store_joke_in_db(joke_data)
            
            span.set_attribute("job.status", "success")
            logger.info(
                f"Job {job_id}: Successfully fetched and stored joke {joke_data['id']}, "
                f"trace_id={get_current_trace_id()}"
            )
            
            return {
                "joke_id": joke_data["id"],
                "category": joke_data.get("categories", ["uncategorized"])[0] if joke_data.get("categories") else "uncategorized",
                "trace_id": get_current_trace_id(),
                "span_id": get_current_span_id()
            }
            
        except Exception as e:
            span.set_attribute("job.status", "error")
            span.set_attribute("error.type", type(e).__name__)
            logger.error(
                f"Job {job_id}: Failed to fetch joke (attempt {attempt}): {e}, "
                f"trace_id={get_current_trace_id()}"
            )
            raise


async def _fetch_joke_from_api(category: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch joke from Chuck Norris API with custom span.
    
    Args:
        category: Optional category filter
        
    Returns:
        Joke data dictionary
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span("api.chuck_norris.fetch_joke") as span:
        url = "https://api.chucknorris.io/jokes/random"
        if category:
            url += f"?category={category}"
        
        span.set_attribute("http.url", url)
        span.set_attribute("api.provider", "chucknorris.io")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            joke_data = response.json()
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("joke.id", joke_data["id"])
            
            return joke_data


async def _store_joke_in_db(joke_data: Dict[str, Any]) -> None:
    """
    Store joke in database with custom span.
    
    Args:
        joke_data: Joke data to store
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span("db.store_joke") as span:
        span.set_attribute("db.operation", "upsert")
        span.set_attribute("db.table", "chuck_norris_jokes")
        span.set_attribute("joke.id", joke_data["id"])
        
        async with AsyncSessionLocal() as session:
            # Check if joke already exists
            existing = await session.execute(
                select(ChuckNorrisJoke).where(ChuckNorrisJoke.joke_id == joke_data["id"])
            )
            
            if existing.scalar_one_or_none():
                span.set_attribute("db.record_exists", True)
                logger.info(f"Joke {joke_data['id']} already exists in database")
                return
            
            # Create new joke record
            joke = ChuckNorrisJoke(
                joke_id=joke_data["id"],
                joke_text=joke_data["value"],
                category=joke_data.get("categories", ["uncategorized"])[0] if joke_data.get("categories") else "uncategorized",
                icon_url=joke_data.get("icon_url"),
                url=joke_data.get("url")
            )
            
            session.add(joke)
            await session.commit()
            
            span.set_attribute("db.record_exists", False)
            span.set_attribute("db.record_created", True)


@app.task(
    queue="traced_processing",
    pass_context=True,
)
async def traced_process_data(
    context,
    data: Dict[str, Any],
    processing_steps: int = 3,
    trace_context: Optional[Dict[str, str]] = None
):
    """
    Example task that demonstrates multi-step processing with tracing.
    
    Args:
        context: Procrastinate job context
        data: Data to process
        processing_steps: Number of processing steps to simulate
        trace_context: OpenTelemetry trace context
    """
    # Extract and set trace context if provided
    if trace_context:
        extract_trace_context(trace_context)
    
    job_id = context.job.id
    
    with trace_job_execution(
        "process_data",
        job_id=job_id,
        steps=processing_steps,
        data_size=len(str(data))
    ) as span:
        
        logger.info(
            f"Job {job_id}: Starting data processing with {processing_steps} steps, "
            f"trace_id={get_current_trace_id()}"
        )
        
        results = []
        
        for step in range(processing_steps):
            with get_tracer().start_as_current_span(f"process_step_{step + 1}") as step_span:
                step_span.set_attribute("step.number", step + 1)
                step_span.set_attribute("step.total", processing_steps)
                
                # Simulate processing work
                await asyncio.sleep(0.5)
                
                step_result = {
                    "step": step + 1,
                    "processed_at": f"step_{step + 1}",
                    "trace_id": get_current_trace_id(),
                    "span_id": get_current_span_id()
                }
                
                results.append(step_result)
                step_span.set_attribute("step.result", str(step_result))
                
                logger.info(
                    f"Job {job_id}: Completed step {step + 1}/{processing_steps}, "
                    f"trace_id={get_current_trace_id()}"
                )
        
        span.set_attribute("job.steps_completed", len(results))
        span.set_attribute("job.status", "success")
        
        return {
            "job_id": job_id,
            "steps_completed": len(results),
            "results": results,
            "trace_id": get_current_trace_id()
        }


# Convenience functions for deferring traced jobs

async def defer_traced_joke_fetch(category: Optional[str] = None) -> str:
    """
    Defer a traced joke fetch job with proper trace context propagation.
    
    Args:
        category: Optional joke category
        
    Returns:
        Job ID
    """
    # Create trace context for the job
    trace_context = trace_job_defer("traced_fetch_joke", category=category)
    
    # Defer the job with trace context
    job_id = await traced_fetch_joke.defer_async(
        category=category,
        trace_context=trace_context
    )
    
    logger.info(
        f"Deferred traced joke fetch job {job_id} with trace_id={get_current_trace_id()}"
    )
    
    return job_id


def defer_traced_joke_fetch_sync(category: Optional[str] = None) -> str:
    """
    Synchronous version of defer_traced_joke_fetch.
    
    Args:
        category: Optional joke category
        
    Returns:
        Job ID
    """
    # Create trace context for the job
    trace_context = trace_job_defer("traced_fetch_joke", category=category)
    
    # Defer the job with trace context
    job_id = traced_fetch_joke.defer(
        category=category,
        trace_context=trace_context
    )
    
    logger.info(
        f"Deferred traced joke fetch job {job_id} with trace_id={get_current_trace_id()}"
    )
    
    return job_id


async def defer_traced_data_processing(
    data: Dict[str, Any], 
    processing_steps: int = 3
) -> str:
    """
    Defer a traced data processing job with proper trace context propagation.
    
    Args:
        data: Data to process
        processing_steps: Number of processing steps
        
    Returns:
        Job ID
    """
    # Create trace context for the job
    trace_context = trace_job_defer(
        "traced_process_data", 
        data=data, 
        processing_steps=processing_steps
    )
    
    # Defer the job with trace context
    job_id = await traced_process_data.defer_async(
        data=data,
        processing_steps=processing_steps,
        trace_context=trace_context
    )
    
    logger.info(
        f"Deferred traced data processing job {job_id} with trace_id={get_current_trace_id()}"
    )
    
    return job_id
