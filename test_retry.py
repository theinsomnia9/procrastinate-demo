#!/usr/bin/env python3
"""
Test script for demonstrating Procrastinate retry functionality with PostgreSQL.

This script provides easy commands to:
1. Enqueue failing tasks for retry testing
2. Monitor retry attempts in real-time
3. Query the database to verify retry behavior
4. Clean up test data

Usage:
    python test_retry.py enqueue [--fail-attempts N]
    python test_retry.py monitor
    python test_retry.py status
    python test_retry.py cleanup
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime
from typing import List, Dict, Any

# Add the app directory to Python path
sys.path.insert(0, '/home/homie/projects/procrastinate-demo')

from app.procrastinate_app import app
from app.tasks import failing_task_for_retry_testing, enqueue_failing_task
from app.database import AsyncSessionLocal
from app.models import ChuckNorrisJoke
from sqlalchemy import select, func, desc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def enqueue_failing_task_cmd(fail_attempts: int = 4):
    """Enqueue a failing task for retry testing."""
    print(f"🚀 Enqueueing failing task (will fail {fail_attempts} times before succeeding)...")
    
    try:
        # Open the app connection
        async with app.open_async():
            # Directly enqueue the failing task
            job = await failing_task_for_retry_testing.defer_async(fail_attempts=fail_attempts)
            
            print(f"✅ Successfully enqueued failing task!")
            print(f"   Job ID: {job}")
            print(f"   Queue: test_failures")
            print(f"   Will fail: {fail_attempts} times")
            print(f"   Max attempts: 5")
            print(f"   Expected success on attempt: {fail_attempts + 1}")
            print()
            print("💡 To monitor progress, run: python test_retry.py monitor")
            print("💡 To check status, run: python test_retry.py status")
            
            return job
        
    except Exception as e:
        print(f"❌ Failed to enqueue task: {e}")
        logger.error(f"Failed to enqueue task: {e}", exc_info=True)
        return None


async def monitor_jobs():
    """Monitor job execution in real-time."""
    print("👀 Monitoring retry test jobs (press Ctrl+C to stop)...")
    print("=" * 60)
    
    try:
        while True:
            # Get retry test logs from database
            async with AsyncSessionLocal() as session:
                # Query retry test logs
                result = await session.execute(
                    select(ChuckNorrisJoke)
                    .where(ChuckNorrisJoke.category == "retry_test")
                    .order_by(desc(ChuckNorrisJoke.updated_at))
                    .limit(10)
                )
                logs = result.scalars().all()
                
                if logs:
                    print(f"\n📊 Latest retry attempts ({datetime.now().strftime('%H:%M:%S')}):")
                    for log in logs:
                        print(f"   {log.joke_text} - {log.updated_at.strftime('%H:%M:%S')}")
                else:
                    print(f"⏳ No retry attempts yet... ({datetime.now().strftime('%H:%M:%S')})")
            
            # Check Procrastinate job status (simplified)
            print(f"\n📋 Job status will be shown by worker logs")
            
            await asyncio.sleep(2)  # Check every 2 seconds
            
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped.")
    except Exception as e:
        print(f"❌ Monitoring error: {e}")
        logger.error(f"Monitoring error: {e}", exc_info=True)


async def show_status():
    """Show current status of retry test jobs."""
    print("📊 Retry Test Status Report")
    print("=" * 40)
    
    try:
        # Get retry test logs from database
        async with AsyncSessionLocal() as session:
            # Count retry attempts by job
            result = await session.execute(
                select(
                    ChuckNorrisJoke.url,
                    func.count(ChuckNorrisJoke.joke_id).label('attempt_count'),
                    func.max(ChuckNorrisJoke.joke_text).label('latest_log'),
                    func.max(ChuckNorrisJoke.updated_at).label('last_update')
                )
                .where(ChuckNorrisJoke.category == "retry_test")
                .group_by(ChuckNorrisJoke.url)
                .order_by(desc('last_update'))
            )
            
            retry_stats = result.all()
            
            if retry_stats:
                print(f"\n🔄 Retry Attempts by Job:")
                for stat in retry_stats:
                    job_id = stat.url.split('/')[-1] if stat.url else "unknown"
                    print(f"   Job {job_id}: {stat.attempt_count} attempts")
                    print(f"      Latest: {stat.latest_log}")
                    print(f"      Last update: {stat.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
                    print()
            else:
                print("   No retry attempts found.")
        
        print(f"📋 Procrastinate Jobs:")
        print("   Job status can be monitored through worker logs and retry attempt logs above.")
            
    except Exception as e:
        print(f"❌ Failed to get status: {e}")
        logger.error(f"Failed to get status: {e}", exc_info=True)


async def cleanup_test_data():
    """Clean up retry test data from database."""
    print("🧹 Cleaning up retry test data...")
    
    try:
        async with AsyncSessionLocal() as session:
            # Delete retry test logs
            result = await session.execute(
                select(func.count(ChuckNorrisJoke.joke_id))
                .where(ChuckNorrisJoke.category == "retry_test")
            )
            count_before = result.scalar()
            
            if count_before > 0:
                await session.execute(
                    ChuckNorrisJoke.__table__.delete()
                    .where(ChuckNorrisJoke.category == "retry_test")
                )
                await session.commit()
                
                print(f"✅ Deleted {count_before} retry test log entries from database.")
            else:
                print("   No retry test logs found to clean up.")
        
        print("🎉 Cleanup complete!")
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        logger.error(f"Cleanup failed: {e}", exc_info=True)


async def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Test Procrastinate retry functionality with PostgreSQL"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Enqueue command
    enqueue_parser = subparsers.add_parser('enqueue', help='Enqueue a failing task')
    enqueue_parser.add_argument(
        '--fail-attempts', 
        type=int, 
        default=4,
        help='Number of attempts that should fail before succeeding (default: 4)'
    )
    
    # Monitor command
    subparsers.add_parser('monitor', help='Monitor retry attempts in real-time')
    
    # Status command
    subparsers.add_parser('status', help='Show current status of retry tests')
    
    # Cleanup command
    subparsers.add_parser('cleanup', help='Clean up retry test data')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    print("🔧 Procrastinate Retry Test Tool")
    print("=" * 35)
    
    try:
        if args.command == 'enqueue':
            await enqueue_failing_task_cmd(args.fail_attempts)
        elif args.command == 'monitor':
            await monitor_jobs()
        elif args.command == 'status':
            await show_status()
        elif args.command == 'cleanup':
            await cleanup_test_data()
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\n👋 Operation cancelled by user.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        logger.error(f"Unexpected error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
