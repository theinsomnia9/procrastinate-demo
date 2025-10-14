import procrastinate
from app.config import get_settings

settings = get_settings()

# Initialize Procrastinate app with PostgreSQL connector
app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(
        conninfo=settings.procrastinate_database_url,
    ),
    import_paths=["app.tasks"],
)


def get_retry_strategy(attempt: int) -> dict:
    """
    Calculate exponential backoff delay for retry attempts.
    
    Formula: delay = min(base_delay * (2 ^ attempt), max_delay)
    
    Args:
        attempt: Current retry attempt number (0-indexed)
        
    Returns:
        Dictionary with schedule_in parameter for Procrastinate
    """
    delay = min(
        settings.retry_base_delay * (2 ** attempt),
        settings.retry_max_delay
    )
    return {"seconds": int(delay)}
