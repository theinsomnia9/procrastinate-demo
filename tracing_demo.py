#!/usr/bin/env python3
"""
OpenTelemetry + Procrastinate Demo Script

This script demonstrates:
1. Setting up OpenTelemetry tracing with Jaeger
2. Deferring Procrastinate jobs with trace context propagation
3. Tracking jobs from defer to completion
4. Viewing traces in Jaeger UI

Usage:
    python tracing_demo.py [--setup-db] [--defer-jobs] [--run-worker]
"""

import asyncio
import logging
import sys
import argparse
from typing import List

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import our modules
from app.tracing import setup_tracing, get_current_trace_id, get_tracer
from app.traced_tasks import (
    defer_traced_joke_fetch,
    defer_traced_data_processing,
    traced_fetch_joke,
    traced_process_data
)
from app.procrastinate_app import app


async def setup_database():
    """Initialize the database schema."""
    logger.info("Setting up database schema...")
    
    # This would typically be done with Alembic migrations
    # For demo purposes, we'll assume the schema exists
    logger.info("Database schema setup complete")


async def defer_demo_jobs() -> List[str]:
    """
    Defer several demo jobs with tracing enabled.
    
    Returns:
        List of job IDs
    """
    tracer = get_tracer()
    job_ids = []
    
    with tracer.start_as_current_span("demo.defer_jobs") as span:
        span.set_attribute("demo.operation", "defer_jobs")
        
        logger.info(f"Starting job deferral demo, trace_id={get_current_trace_id()}")
        
        # Defer joke fetch jobs
        joke_categories = ["dev", "animal", None]  # None = random
        
        for i, category in enumerate(joke_categories):
            job_id = await defer_traced_joke_fetch(category=category)
            job_ids.append(job_id)
            span.set_attribute(f"job.{i}.id", job_id)
            span.set_attribute(f"job.{i}.type", "joke_fetch")
            span.set_attribute(f"job.{i}.category", category or "random")
        
        # Defer data processing jobs
        demo_data = [
            {"type": "user_data", "records": 100},
            {"type": "analytics", "events": 500},
            {"type": "reports", "queries": 25}
        ]
        
        for i, data in enumerate(demo_data):
            job_id = await defer_traced_data_processing(
                data=data, 
                processing_steps=3
            )
            job_ids.append(job_id)
            span.set_attribute(f"job.{i + len(joke_categories)}.id", job_id)
            span.set_attribute(f"job.{i + len(joke_categories)}.type", "data_processing")
        
        span.set_attribute("jobs.total_deferred", len(job_ids))
        
        logger.info(
            f"Deferred {len(job_ids)} jobs with trace_id={get_current_trace_id()}: {job_ids}"
        )
    
    return job_ids


async def run_worker_demo():
    """Run the Procrastinate worker to process jobs."""
    logger.info("Starting Procrastinate worker...")
    
    try:
        # Run worker for a limited time (in production, this would run indefinitely)
        await asyncio.wait_for(
            app.run_worker_async(queues=["traced_api_calls", "traced_processing"]),
            timeout=60.0  # Run for 60 seconds
        )
    except asyncio.TimeoutError:
        logger.info("Worker demo completed (timeout reached)")
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")


async def run_full_demo():
    """Run the complete demo: setup, defer jobs, and process them."""
    tracer = get_tracer()
    
    with tracer.start_as_current_span("demo.full_workflow") as span:
        span.set_attribute("demo.type", "full_workflow")
        
        logger.info(f"Starting full demo workflow, trace_id={get_current_trace_id()}")
        
        # Setup database
        await setup_database()
        
        # Defer jobs
        job_ids = await defer_demo_jobs()
        span.set_attribute("demo.jobs_deferred", len(job_ids))
        
        # Give a moment for jobs to be queued
        await asyncio.sleep(1)
        
        # Process jobs
        logger.info("Processing jobs...")
        await run_worker_demo()
        
        logger.info(f"Full demo completed, trace_id={get_current_trace_id()}")


def print_jaeger_info():
    """Print information about accessing Jaeger UI."""
    print("\n" + "="*60)
    print("🔍 JAEGER TRACING INFORMATION")
    print("="*60)
    print("After running this demo, you can view traces in Jaeger:")
    print()
    print("1. Ensure Jaeger is running (see docker-compose.yml)")
    print("2. Open Jaeger UI: http://localhost:16686")
    print("3. Select service: 'procrastinate-demo'")
    print("4. Click 'Find Traces' to see the execution flow")
    print()
    print("You should see:")
    print("- Parent spans for job deferral")
    print("- Child spans for job execution")
    print("- HTTP calls to Chuck Norris API")
    print("- Database operations")
    print("- Processing steps")
    print("="*60)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="OpenTelemetry + Procrastinate Demo")
    parser.add_argument("--setup-db", action="store_true", help="Setup database schema")
    parser.add_argument("--defer-jobs", action="store_true", help="Defer demo jobs only")
    parser.add_argument("--run-worker", action="store_true", help="Run worker only")
    parser.add_argument("--jaeger-endpoint", default="http://localhost:14268/api/traces", 
                       help="Jaeger collector endpoint")
    parser.add_argument("--console", action="store_true", help="Enable console tracing output")
    
    args = parser.parse_args()
    
    # Initialize OpenTelemetry
    logger.info("Initializing OpenTelemetry tracing...")
    setup_tracing(
        service_name="procrastinate-demo",
        jaeger_endpoint=args.jaeger_endpoint,
        enable_console=args.console
    )
    
    try:
        if args.setup_db:
            await setup_database()
        elif args.defer_jobs:
            job_ids = await defer_demo_jobs()
            print(f"Deferred jobs: {job_ids}")
        elif args.run_worker:
            await run_worker_demo()
        else:
            # Run full demo
            await run_full_demo()
        
        print_jaeger_info()
        
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
