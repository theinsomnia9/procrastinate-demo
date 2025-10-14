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
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
