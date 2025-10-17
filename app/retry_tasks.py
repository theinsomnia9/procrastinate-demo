"""
Retry demonstration tasks with OpenTelemetry tracing.

This module contains tasks that intentionally fail multiple times
to demonstrate retry behavior with distributed tracing.
"""

import asyncio
import logging
from typing import Dict, Optional

from app.procrastinate_app import app, ExponentialBackoffStrategy
from app.tracing import extract_trace_context, get_tracer

logger = logging.getLogger(__name__)


class SimulatedFailureError(Exception):
    """Custom exception for simulating failures."""
    pass


@app.task(
    queue="retry_demo",
    retry=ExponentialBackoffStrategy(
        max_attempts=5,  # Will fail 4 times, succeed on 5th
        base_delay=1.0,  # Start with 1 second delay
        max_delay=30.0,  # Cap at 30 seconds
        retry_exceptions=[SimulatedFailureError, ConnectionError, TimeoutError],
    ),
    pass_context=True,
)
async def flaky_traced_task(
    context,
    task_name: str,
    fail_until_attempt: int = 5,
    trace_context: Optional[Dict[str, str]] = None
):
    """
    A task that fails multiple times before succeeding, with full tracing.
    
    Args:
        context: Procrastinate job context
        task_name: Name of the task for identification
        fail_until_attempt: Attempt number on which to succeed (1-indexed)
        trace_context: OpenTelemetry trace context
    """
    # Extract and set trace context if provided
    if trace_context:
        extract_trace_context(trace_context)
    
    job_id = context.job.id
    attempt = context.job.attempts
    
    tracer = get_tracer()
    
    with tracer.start_as_current_span("flaky_task_execution") as span:
        span.set_attribute("job.id", str(job_id))
        span.set_attribute("job.name", task_name)
        span.set_attribute("job.attempt", attempt)
        span.set_attribute("job.max_attempts", 5)
        span.set_attribute("job.fail_until_attempt", fail_until_attempt)
        
        from opentelemetry import trace
        current_span = trace.get_current_span()
        trace_id = current_span.get_span_context().trace_id if current_span.get_span_context().is_valid else 0
        
        logger.info(
            f"Job {job_id} ({task_name}): Attempt {attempt}/5, "
            f"trace_id={trace_id:032x}"
        )
        
        # Simulate some work
        with tracer.start_as_current_span("simulate_work") as work_span:
            work_span.set_attribute("work.duration_ms", 500)
            await asyncio.sleep(0.5)
        
        # Fail on attempts 1-4, succeed on attempt 5
        if attempt < fail_until_attempt:
            error_types = [
                ("connection_error", ConnectionError("Database connection failed")),
                ("timeout_error", TimeoutError("Request timed out")),
                ("simulated_error", SimulatedFailureError("Simulated failure for demo")),
                ("network_error", ConnectionError("Network unreachable")),
            ]
            
            error_type, error = error_types[min(attempt - 1, len(error_types) - 1)]
            
            span.set_attribute("job.status", "failed")
            span.set_attribute("job.error_type", error_type)
            span.set_attribute("job.will_retry", True)
            span.record_exception(error)
            
            logger.error(
                f"Job {job_id} ({task_name}): Attempt {attempt} failed with {error_type}: {error}"
            )
            
            raise error
        
        # Success on the final attempt
        span.set_attribute("job.status", "success")
        span.set_attribute("job.final_attempt", True)
        
        result = {
            "task_name": task_name,
            "job_id": job_id,
            "successful_attempt": attempt,
            "total_attempts": attempt,
            "trace_id": f"{trace_id:032x}",
            "message": f"Task {task_name} succeeded after {attempt} attempts!"
        }
        
        logger.info(
            f"Job {job_id} ({task_name}): SUCCESS on attempt {attempt}! "
            f"Result: {result['message']}"
        )
        
        return result
