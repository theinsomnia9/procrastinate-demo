#!/usr/bin/env python3
"""
Simple OpenTelemetry + Procrastinate Example

This script shows the core concepts of passing traceparent ID through 
extra args to track a job from defer to completion.
"""

import asyncio
import logging
from typing import Dict, Optional

from app.tracing import setup_tracing, inject_trace_context, extract_trace_context, get_tracer
from app.procrastinate_app import app

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.task(pass_context=True)
async def simple_traced_task(
    context, 
    message: str,
    trace_context: Optional[Dict[str, str]] = None
):
    """
    A simple task that demonstrates trace context propagation.
    
    Args:
        context: Procrastinate job context
        message: Message to process
        trace_context: OpenTelemetry trace context (the key part!)
    """
    # Extract and activate the trace context from the parent
    if trace_context:
        extract_trace_context(trace_context)
    
    # Now we're in the same trace as the caller!
    tracer = get_tracer()
    
    print(context)
    
    with tracer.start_as_current_span("simple_task_execution") as span:
        span.set_attribute("job.id", str(context.job.id))
        span.set_attribute("job.message", message)
        
        logger.info(f"Processing message: {message} in job {context.job.id}")
        
        # Simulate some work
        await asyncio.sleep(1)
        
        result = f"Processed: {message}"
        span.set_attribute("job.result", result)
        
        return result


async def defer_traced_job(message: str) -> str:
    """
    Defer a job with trace context propagation.
    
    This is the key pattern: capture current trace context and pass it as an argument.
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span("defer_simple_task") as span:
        span.set_attribute("job.message", message)
        
        # IMPORTANT: Capture current trace context
        trace_context = inject_trace_context()
        
        # Defer the job with trace context as an extra argument
        job_id = await simple_traced_task.defer_async(
            message=message,
            trace_context=trace_context  # This is the magic!
        )
        
        span.set_attribute("job.id", str(job_id))
        logger.info(f"Deferred job {job_id} with trace context")
        
        return job_id


async def main():
    """Main example."""
    # Initialize tracing
    setup_tracing(service_name="simple-example")
    
    tracer = get_tracer()
    
    # Open the Procrastinate app
    async with app.open_async():
        # Create a root span for our workflow
        with tracer.start_as_current_span("example_workflow") as span:
            logger.info("Starting traced workflow")
            
            # Defer some jobs
            job_ids = []
            for i in range(3):
                job_id = await defer_traced_job(f"Hello from job {i}")
                job_ids.append(job_id)
            
            span.set_attribute("jobs.deferred", len(job_ids))
            logger.info(f"Deferred {len(job_ids)} jobs: {job_ids}")
            
            print("\n" + "="*50)
            print("Jobs deferred with trace context!")
            print("="*50)
            print("To see the traces:")
            print("1. Start Jaeger: docker-compose up jaeger")
            print("2. Run worker: procrastinate worker")
            print("3. Open Jaeger UI: http://localhost:16686")
            print("4. Look for service 'simple-example'")
            print("="*50)


if __name__ == "__main__":
    asyncio.run(main())
