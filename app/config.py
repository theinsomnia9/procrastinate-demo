from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    database_url: str
    procrastinate_database_url: str
    api_base_url: str = "https://api.chucknorris.io"
    
    # Retry configuration
    max_retries: int = 5
    retry_base_delay: float = 2.0  # Base delay in seconds for exponential backoff
    retry_max_delay: float = 300.0  # Max delay in seconds (5 minutes)
    
    # Job timeout configuration
    job_timeout: int = 300  # Maximum time a job can run (5 minutes)
    
    # Worker configuration
    worker_concurrency: int = 10  # Number of concurrent jobs per worker
    worker_timeout: int = 30  # Graceful shutdown timeout in seconds
    
    # Stalled job detection
    stalled_job_check_interval: int = 10  # Check every 10 minutes (cron: */10)
    stalled_job_threshold: int = 600  # Consider job stalled after 10 minutes
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
