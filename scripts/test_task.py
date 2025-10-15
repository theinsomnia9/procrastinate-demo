#!/usr/bin/env python
"""
Test script to submit multiple tasks and monitor their execution.

Usage:
    python scripts/test_task.py [number_of_tasks]
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.procrastinate_app import app as procrastinate_app
from app.tasks import fetch_and_cache_joke


async def main():
    """Submit test tasks."""
    num_tasks = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    
    print(f"Submitting {num_tasks} test tasks...")
    
    async with procrastinate_app.open_async():
        job_ids = []
        
        for i in range(num_tasks):
            # Alternate between random and dev category
            category = "dev" if i % 2 == 0 else None
            job = await fetch_and_cache_joke.defer_async(category=category)
            job_ids.append(job.id)
            print(f"✓ Submitted job {job.id} (category: {category or 'random'})")
        
        print(f"\n✅ Successfully submitted {len(job_ids)} tasks")
        print(f"Job IDs: {job_ids}")
        print("\nMonitor progress:")
        print("- Check logs in the main application")
        print("- Query pgAdmin: SELECT * FROM procrastinate_jobs;")
        print("- Use API: curl http://localhost:8000/jobs/<job_id>")


if __name__ == "__main__":
    asyncio.run(main())
