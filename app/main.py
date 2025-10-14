import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db, init_db
from app.models import ChuckNorrisJoke
from app.procrastinate_app import app as procrastinate_app
from app.tasks import fetch_and_cache_joke
from app.schemas import (
    JokeResponse,
    TaskRequest,
    TaskResponse,
    JobStatusResponse,
    StatsResponse,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    
    Handles:
    - Database initialization
    - Procrastinate schema setup
    - Worker lifecycle management
    - Graceful shutdown
    """
    logger.info("Starting application...")
    
    # Initialize database tables
    await init_db()
    logger.info("Database tables initialized")
    
    # Open Procrastinate app and apply schema
    async with procrastinate_app.open_async():
        # Apply Procrastinate schema
        try:
            await procrastinate_app.schema_manager.apply_schema_async()
            logger.info("Procrastinate schema applied")
        except Exception as e:
            logger.warning(f"Schema already exists or error applying: {e}")
        
        # Start the worker in the background
        worker_task = asyncio.create_task(
            procrastinate_app.run_worker_async(
                install_signal_handlers=False,
                queues=["api_calls", "default"],
                concurrency=10,              # Handle 10 jobs concurrently
                shutdown_graceful_timeout=30, # Abort jobs after 30s on shutdown
                listen_notify=True,          # Real-time job notifications
            )
        )
        logger.info("Procrastinate worker started with concurrency=10")
        
        yield
        
        # Shutdown: Cancel worker and wait for graceful shutdown
        logger.info("Shutting down worker...")
        worker_task.cancel()
        try:
            await asyncio.wait_for(worker_task, timeout=30)
            logger.info("Graceful shutdown completed")
        except asyncio.TimeoutError:
            logger.warning("Worker shutdown timeout - forcing shutdown")
        except asyncio.CancelledError:
            logger.info("Worker cancelled successfully")


# Create FastAPI app
app = FastAPI(
    title="Procrastinate Demo API",
    description="A bulletproof task scheduling system using FastAPI and Procrastinate",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with API documentation."""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Procrastinate Demo API</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            h1 { color: #333; }
            .endpoint {
                background: white;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .method {
                display: inline-block;
                padding: 3px 8px;
                border-radius: 3px;
                font-weight: bold;
                margin-right: 10px;
            }
            .get { background-color: #61affe; color: white; }
            .post { background-color: #49cc90; color: white; }
            code {
                background-color: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
            }
        </style>
    </head>
    <body>
        <h1>🚀 Procrastinate Demo API</h1>
        <p>A production-ready task scheduling system with bulletproof retry strategies.</p>
        
        <h2>Available Endpoints:</h2>
        
        <div class="endpoint">
            <span class="method post">POST</span>
            <code>/tasks/fetch-joke</code>
            <p>Trigger a task to fetch and cache a Chuck Norris joke</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/jokes</code>
            <p>List all cached jokes with pagination</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/jokes/{joke_id}</code>
            <p>Get a specific joke by ID</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/jobs/{job_id}</code>
            <p>Check the status of a specific job</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span>
            <code>/stats</code>
            <p>Get statistics about cached jokes and jobs</p>
        </div>
        
        <h2>Monitoring:</h2>
        <ul>
            <li><a href="/docs">Interactive API Documentation (Swagger)</a></li>
            <li><a href="http://localhost:5050" target="_blank">pgAdmin (Database UI)</a></li>
        </ul>
        
        <h2>Features:</h2>
        <ul>
            <li>✅ Exponential backoff retry strategy</li>
            <li>✅ Automatic recovery from crashes</li>
            <li>✅ Periodic task scheduling</li>
            <li>✅ Stalled job detection and retry</li>
            <li>✅ Idempotent operations</li>
            <li>✅ Comprehensive error handling</li>
        </ul>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/tasks/fetch-joke", response_model=TaskResponse)
async def trigger_fetch_joke(request: TaskRequest = TaskRequest()):
    """
    Trigger a task to fetch and cache a joke from the API.
    
    The task will be executed asynchronously with automatic retries
    on failure using exponential backoff.
    """
    try:
        job_id = await fetch_and_cache_joke.defer_async(category=request.category)
        
        return TaskResponse(
            job_id=job_id,
            status="queued",
            message=f"Job {job_id} queued successfully. Category: {request.category or 'random'}"
        )
    except Exception as e:
        logger.error(f"Failed to queue job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue job: {str(e)}")


@app.get("/jokes", response_model=List[JokeResponse])
async def list_jokes(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Number of records to return"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: AsyncSession = Depends(get_db),
):
    """
    List cached jokes with pagination and optional category filter.
    """
    query = select(ChuckNorrisJoke).order_by(ChuckNorrisJoke.created_at.desc())
    
    if category:
        query = query.where(ChuckNorrisJoke.category == category)
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    jokes = result.scalars().all()
    
    return jokes


@app.get("/jokes/{joke_id}", response_model=JokeResponse)
async def get_joke(joke_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get a specific joke by its joke_id.
    """
    query = select(ChuckNorrisJoke).where(ChuckNorrisJoke.joke_id == joke_id)
    result = await db.execute(query)
    joke = result.scalar_one_or_none()
    
    if not joke:
        raise HTTPException(status_code=404, detail="Joke not found")
    
    return joke


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: int):
    """
    Get the status of a specific job.
    """
    try:
        job = await procrastinate_app.job_manager.get_job_status_async(job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobStatusResponse(
            job_id=job.id,
            task_name=job.task_name,
            status=job.status,
            attempts=job.attempts,
            scheduled_at=job.scheduled_at,
            started_at=job.started_at,
            queue_name=job.queue_name,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@app.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """
    Get statistics about cached jokes and recent jobs.
    """
    # Count total jokes
    total_query = select(func.count(ChuckNorrisJoke.id))
    total_result = await db.execute(total_query)
    total_jokes = total_result.scalar()
    
    # Count by category
    category_query = select(
        ChuckNorrisJoke.category,
        func.count(ChuckNorrisJoke.id).label("count")
    ).group_by(ChuckNorrisJoke.category)
    category_result = await db.execute(category_query)
    categories = {
        row.category or "uncategorized": row.count
        for row in category_result
    }
    
    # Get recent jobs count (this is a simplified version)
    # In production, you'd query the procrastinate_jobs table
    recent_jobs = 0
    
    return StatsResponse(
        total_jokes=total_jokes,
        categories=categories,
        recent_jobs=recent_jobs,
    )


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    """
    return {
        "status": "healthy",
        "service": "procrastinate-demo",
        "version": "1.0.0"
    }
