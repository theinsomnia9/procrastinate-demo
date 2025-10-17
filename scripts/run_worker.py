#!/usr/bin/env python
"""
Run a standalone Procrastinate worker.

This allows running the worker separately from the FastAPI server,
which is useful for scaling or development.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.procrastinate_app import app as procrastinate_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Run the Procrastinate worker."""
    logger.info("Starting standalone Procrastinate worker...")
    
    async with procrastinate_app.open_async():
        logger.info("Worker connected to database")
        logger.info("Listening on queues: api_calls, default, traced_api_calls, traced_processing, retry_demo")
        
        try:
            await procrastinate_app.run_worker_async(
                queues=["api_calls", "default", "traced_api_calls", "traced_processing", "retry_demo"],
                wait=True,
            )
        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown complete")
