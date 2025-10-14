#!/usr/bin/env python
"""
Initialize the database and apply Procrastinate schema.

This script can be run standalone to set up the database before starting the application.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db
from app.procrastinate_app import app as procrastinate_app


async def main():
    """Initialize database and Procrastinate schema."""
    print("Initializing database tables...")
    await init_db()
    print("✓ Database tables created")
    
    print("\nApplying Procrastinate schema...")
    async with procrastinate_app.open_async():
        try:
            await procrastinate_app.schema_manager.apply_schema_async()
            print("✓ Procrastinate schema applied")
        except Exception as e:
            print(f"⚠ Schema may already exist: {e}")
    
    print("\n✅ Database initialization complete!")


if __name__ == "__main__":
    asyncio.run(main())
