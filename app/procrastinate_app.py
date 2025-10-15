import procrastinate
from procrastinate.retry import BaseRetryStrategy
from typing import Optional
from app.config import get_settings

settings = get_settings()


class ExponentialBackoffStrategy(BaseRetryStrategy):
    """
    True exponential backoff retry strategy with jitter.
    
    Formula: delay = min(base_delay * (2 ^ attempts), max_delay)
    
    This ensures tasks retry with exponentially increasing delays,
    preventing thundering herd and giving failing services time to recover.
    """
    
    def __init__(
        self,
        max_attempts: int = 5,
        base_delay: float = 2.0,
        max_delay: float = 300.0,
        retry_exceptions: Optional[list] = None,
    ):
        """
        Initialize exponential backoff strategy.
        
        Args:
            max_attempts: Maximum number of retry attempts (including initial)
            base_delay: Base delay in seconds (multiplied by 2^attempt)
            max_delay: Maximum delay cap in seconds
            retry_exceptions: List of exception types to retry on (None = all)
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retry_exceptions = retry_exceptions
    
    def get_retry_decision(
        self,
        *,
        exception: Optional[Exception] = None,
        job,
    ):
        """
        Calculate the delay before next retry (new API).
        
        Args:
            exception: The exception that caused the failure
            job: The job object with attempts information
            
        Returns:
            RetryDecision or None to stop retrying
        """
        from procrastinate.retry import RetryDecision
        
        attempts = job.attempts
        
        # Check if we've exceeded max attempts
        if attempts >= self.max_attempts:
            return None
        
        # Check if exception type should be retried
        if self.retry_exceptions is not None and exception is not None:
            if not any(isinstance(exception, exc_type) for exc_type in self.retry_exceptions):
                return None
        
        # Calculate exponential delay: base_delay * (2 ^ attempts)
        delay_seconds = min(self.base_delay * (2 ** attempts), self.max_delay)
        
        return RetryDecision(retry_in=int(delay_seconds))
    
    def get_schedule_in(
        self,
        *,
        exception: Optional[Exception] = None,
        attempts: int,
    ) -> Optional[dict]:
        """
        Calculate the delay before next retry (deprecated, for backwards compatibility).
        
        Args:
            exception: The exception that caused the failure
            attempts: Number of attempts so far (0-indexed)
            
        Returns:
            Dictionary with 'seconds' key for delay, or None to stop retrying
        """
        # Check if we've exceeded max attempts
        if attempts >= self.max_attempts:
            return None
        
        # Check if exception type should be retried
        if self.retry_exceptions is not None and exception is not None:
            if not any(isinstance(exception, exc_type) for exc_type in self.retry_exceptions):
                return None
        
        # Calculate exponential delay: base_delay * (2 ^ attempts)
        delay = min(self.base_delay * (2 ** attempts), self.max_delay)
        
        return {"seconds": int(delay)}


# Initialize Procrastinate app with PostgreSQL connector
app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(
        conninfo=settings.procrastinate_database_url,
        # Enable connection pooling for better performance
        max_size=20,  # Note: psycopg3 uses 'max_size' not 'maxsize'
    ),
    import_paths=["app.tasks"],
)
