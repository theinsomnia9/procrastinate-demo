from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class JokeBase(BaseModel):
    """Base schema for joke data."""
    joke_id: str = Field(..., description="Unique identifier for the joke")
    category: Optional[str] = Field(None, description="Joke category")
    joke_text: str = Field(..., description="The joke text")
    icon_url: Optional[str] = Field(None, description="URL to joke icon")
    url: Optional[str] = Field(None, description="URL to joke page")


class JokeResponse(JokeBase):
    """Response schema for joke data."""
    id: int = Field(..., description="Database ID")
    created_at: datetime = Field(..., description="When the joke was cached")
    updated_at: datetime = Field(..., description="When the joke was last updated")
    
    class Config:
        from_attributes = True


class TaskRequest(BaseModel):
    """Request schema for triggering a task."""
    category: Optional[str] = Field(None, description="Optional category filter for jokes")


class TaskResponse(BaseModel):
    """Response schema for task submission."""
    job_id: int = Field(..., description="Procrastinate job ID")
    status: str = Field(..., description="Job status")
    message: str = Field(..., description="Human-readable message")


class JobStatusResponse(BaseModel):
    """Response schema for job status."""
    job_id: int
    task_name: str
    status: str
    attempts: int
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    queue_name: str


class StatsResponse(BaseModel):
    """Response schema for statistics."""
    total_jokes: int = Field(..., description="Total number of cached jokes")
    categories: dict = Field(..., description="Breakdown by category")
    recent_jobs: int = Field(..., description="Number of jobs in last hour")
