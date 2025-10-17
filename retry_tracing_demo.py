#!/usr/bin/env python3
"""
Retry Tracing Demo - OpenTelemetry + Procrastinate

This script demonstrates tracing a job that fails multiple times before succeeding,
showing the complete retry chain in distributed tracing.
"""

import asyncio
import logging
import random
from typing import Dict, Optional

from app.tracing import setup_tracing, inject_trace_context, get_tracer
from app.procrastinate_app import app
from app.retry_tasks import flaky_traced_task

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def defer_flaky_traced_job(task_name: str, fail_until_attempt: int = 5) -> str:
    """
    Defer a flaky traced job with proper trace context propagation.
    
    Args:
        task_name: Name for the task
        fail_until_attempt: Attempt number on which to succeed
        
    Returns:
        Job ID
    """
    tracer = get_tracer()
    
    with tracer.start_as_current_span("defer_flaky_task") as span:
        span.set_attribute("job.name", task_name)
        span.set_attribute("job.fail_until_attempt", fail_until_attempt)
        span.set_attribute("job.expected_attempts", fail_until_attempt)
        
        # IMPORTANT: Capture current trace context
        trace_context = inject_trace_context()
        
        # Defer the job with trace context
        job_id = await flaky_traced_task.defer_async(
            task_name=task_name,
            fail_until_attempt=fail_until_attempt,
            trace_context=trace_context
        )
        
        span.set_attribute("job.id", str(job_id))
        logger.info(
            f"Deferred flaky job {job_id} ({task_name}) - will fail {fail_until_attempt - 1} times"
        )
        
        return job_id


async def main():
    """Main demo function."""
    # Initialize tracing
    setup_tracing(service_name="retry-tracing-demo")
    
    tracer = get_tracer()
    
    # Open the Procrastinate app
    async with app.open_async():
        # Create a root span for our retry demo
        with tracer.start_as_current_span("retry_demo_workflow") as span:
            logger.info("🚀 Starting retry tracing demo...")
            
            # Defer multiple flaky jobs with different failure patterns
            jobs = [
                ("critical_payment_processor", 5),  # Fails 4 times, succeeds on 5th
                ("user_notification_sender", 4),    # Fails 3 times, succeeds on 4th
                ("data_sync_service", 3),           # Fails 2 times, succeeds on 3rd
            ]
            
            job_ids = []
            for task_name, fail_until in jobs:
                job_id = await defer_flaky_traced_job(task_name, fail_until)
                job_ids.append((job_id, task_name, fail_until))
            
            span.set_attribute("jobs.total_deferred", len(job_ids))
            
            print("\n" + "="*70)
            print("🔄 RETRY TRACING DEMO - JOBS DEFERRED")
            print("="*70)
            for job_id, task_name, fail_until in job_ids:
                print(f"📋 Job {job_id}: {task_name}")
                print(f"   └── Will fail {fail_until - 1} times, succeed on attempt {fail_until}")
            
            print("\n🔍 TRACE INFORMATION:")
            from opentelemetry import trace
            current_span = trace.get_current_span()
            if current_span.get_span_context().is_valid:
                print(f"   Root Trace ID: {current_span.get_span_context().trace_id:032x}")
            else:
                print("   Root Trace ID: [No active span]")
            print(f"   Service: retry-tracing-demo")
            
            print("\n📊 WHAT TO EXPECT IN JAEGER:")
            print("   • Root span: retry_demo_workflow")
            print("   • Child spans: defer_flaky_task (for each job)")
            print("   • Retry spans: flaky_task_execution (multiple per job)")
            print("   • Error details: Exception info for each failed attempt")
            print("   • Success span: Final successful execution")
            
            print("\n🚀 NEXT STEPS:")
            print("   1. Ensure worker is running: python scripts/run_worker.py")
            print("   2. Watch worker logs for retry attempts")
            print("   3. Open Jaeger UI: http://localhost:16686")
            print("   4. Search for service: retry-tracing-demo")
            print("   5. Explore the retry trace timeline!")
            print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
