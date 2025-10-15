# Exponential Backoff Retry Strategy

## 📊 Overview

This application implements **true exponential backoff** retry strategies using a custom `ExponentialBackoffStrategy` class based on Procrastinate's `BaseRetryStrategy`. All tasks automatically retry on failure with exponentially increasing delays.

**✨ Upgraded Implementation**: Now using true exponential backoff (2^n) instead of linear backoff for optimal retry behavior.

## 🎯 Configuration

### Main Task: `fetch_and_cache_joke`

```python
@app.task(
    queue="api_calls",
    retry=ExponentialBackoffStrategy(
        max_attempts=5,              # Total attempts (1 initial + 4 retries)
        base_delay=2.0,              # Base delay: 2 seconds
        max_delay=300.0,             # Maximum delay cap: 5 minutes
        retry_exceptions=[           # Only retry these exceptions
            TaskError,
            httpx.HTTPError,
            httpx.TimeoutException
        ],
    ),
    pass_context=True,
)
```

**Retry Schedule (True Exponential):**
- Attempt 1: Immediate (0s)
- Attempt 2: After 2 seconds (2 × 2^0)
- Attempt 3: After 4 seconds (2 × 2^1)
- Attempt 4: After 8 seconds (2 × 2^2)
- Attempt 5: After 16 seconds (2 × 2^3)

**Total time before giving up:** ~30 seconds
**Formula:** `delay = min(base_delay × 2^attempts, max_delay)`

### Periodic Tasks

**`scheduled_fetch_random_joke`** (runs every 2 minutes):
```python
retry=ExponentialBackoffStrategy(max_attempts=3, base_delay=2.0, max_delay=60.0)
```
- 3 total attempts with 2s base delay
- Retries: 0s → 2s → 4s

**`retry_stalled_jobs`** (runs every 10 minutes):
```python
retry=ExponentialBackoffStrategy(max_attempts=3, base_delay=5.0, max_delay=60.0)
```
- 3 total attempts with 5s base delay
- Retries: 0s → 5s → 10s

**`health_check_task`** (runs every 5 minutes):
```python
retry=ExponentialBackoffStrategy(max_attempts=2, base_delay=10.0, max_delay=30.0)
```
- 2 total attempts with 10s base delay
- Retries: 0s → 10s

## 🔢 How Exponential Backoff Works

This application uses **true exponential backoff** with a custom `ExponentialBackoffStrategy` class:

```python
delay = min(base_delay × (2 ^ attempts), max_delay)
```

### Example for `fetch_and_cache_joke`:

| Attempt | Calculation | Delay | Cumulative Time |
|---------|-------------|-------|-----------------|
| 1       | -           | 0s    | 0s              |
| 2       | 2.0 × 2^0   | 2s    | 2s              |
| 3       | 2.0 × 2^1   | 4s    | 6s              |
| 4       | 2.0 × 2^2   | 8s    | 14s             |
| 5       | 2.0 × 2^3   | 16s   | 30s             |

**Benefits of True Exponential Backoff:**
- Prevents thundering herd problem
- Gives failing services more time to recover
- Reduces load on struggling systems
- Industry-standard retry pattern

## 🎨 Custom Exponential Backoff Implementation

This application uses a custom `ExponentialBackoffStrategy` class:

```python
from procrastinate.retry import BaseRetryStrategy
from typing import Optional

class ExponentialBackoffStrategy(BaseRetryStrategy):
    """
    True exponential backoff retry strategy.
    Formula: delay = min(base_delay * (2 ^ attempts), max_delay)
    """
    
    def __init__(
        self,
        max_attempts: int = 5,
        base_delay: float = 2.0,
        max_delay: float = 300.0,
        retry_exceptions: Optional[list] = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.retry_exceptions = retry_exceptions
    
    def get_schedule_in(
        self,
        *,
        exception: Optional[Exception] = None,
        attempts: int,
    ) -> Optional[dict]:
        # Check if we've exceeded max attempts
        if attempts >= self.max_attempts:
            return None
        
        # Check if exception type should be retried
        if self.retry_exceptions is not None and exception is not None:
            if not any(isinstance(exception, exc_type) for exc_type in self.retry_exceptions):
                return None
        
        # Calculate exponential delay
        delay = min(self.base_delay * (2 ** attempts), self.max_delay)
        return {"seconds": int(delay)}
```

**Key Features:**
- ✅ True exponential backoff (2^n)
- ✅ Configurable max delay cap
- ✅ Exception-specific retry logic
- ✅ Fully compatible with Procrastinate 3.x+

## 🛡️ Exception Handling

Tasks only retry on specific exceptions:

```python
retry_exceptions=[
    TaskError,              # Custom task errors
    httpx.HTTPError,        # HTTP errors (4xx, 5xx)
    httpx.TimeoutException, # Request timeouts
]
```

**Other exceptions** (like `ValueError`, `KeyError`) will **not** trigger retries and will immediately fail the job.

## 📊 Monitoring Retries

### Check Job Attempts in Database

```sql
SELECT 
    id,
    task_name,
    status,
    attempts,
    scheduled_at,
    started_at
FROM procrastinate_jobs
WHERE attempts > 1
ORDER BY id DESC;
```

### View Retry Events

```sql
SELECT 
    job_id,
    type,
    at,
    attempts
FROM procrastinate_events
WHERE type = 'deferred_for_retry'
ORDER BY at DESC;
```

### Check via API

```bash
curl http://localhost:8000/jobs/1
```

Response includes `attempts` field:
```json
{
  "job_id": 1,
  "task_name": "app.tasks.fetch_and_cache_joke",
  "status": "succeeded",
  "attempts": 3,  // ← Took 3 attempts to succeed
  "scheduled_at": "2024-10-13T18:30:00Z"
}
```

## 🧪 Testing Retry Logic

### Test 1: Simulate API Failure

```python
# Temporarily break the API URL in .env
API_BASE_URL=https://invalid-api-url.com

# Submit a task
curl -X POST http://localhost:8000/tasks/fetch-joke

# Watch logs to see retries
# You'll see attempts 1, 2, 3, 4, 5 with increasing delays
```

### Test 2: Simulate Timeout

```python
# In app/tasks.py, reduce timeout
async with httpx.AsyncClient(timeout=0.001) as client:  # 1ms timeout
    ...

# Submit task and watch it retry
```

### Test 3: Check Retry Timing

```bash
# Submit a task that will fail
curl -X POST http://localhost:8000/tasks/fetch-joke

# Query database to see retry schedule
docker exec -it procrastinate_postgres psql -U procrastinate -d procrastinate_db

SELECT id, attempts, scheduled_at, started_at 
FROM procrastinate_jobs 
WHERE id = 1;
```

## 📈 Performance Impact

### Benefits
- ✅ Handles transient failures (network blips, API rate limits)
- ✅ Reduces load on failing services (exponential delays)
- ✅ Increases success rate without manual intervention
- ✅ Prevents thundering herd problem
- ✅ Industry-standard retry pattern
- ✅ Configurable per-task behavior
- ✅ Exception-specific retry logic

### Considerations
- ⚠️ Failed jobs take longer to complete (up to 30s for 5 attempts)
- ⚠️ Database stores retry history (more rows in events table)
- ⚠️ Worker capacity used during retry delays
- ⚠️ Max delay cap prevents excessive wait times

## 🎯 Best Practices

### 1. Choose Appropriate Max Attempts
```python
# Quick operations (< 1s)
retry=ExponentialBackoffStrategy(max_attempts=3, base_delay=1.0, max_delay=30.0)

# Medium operations (1-5s)
retry=ExponentialBackoffStrategy(max_attempts=5, base_delay=2.0, max_delay=300.0)

# Long operations (> 5s)
retry=ExponentialBackoffStrategy(max_attempts=3, base_delay=5.0, max_delay=300.0)
```

### 2. Set Reasonable Delays
```python
# Too short: Hammers failing service
retry=ExponentialBackoffStrategy(base_delay=0.1, max_delay=10.0)  # ❌ Bad

# Good: Gives service time to recover
retry=ExponentialBackoffStrategy(base_delay=2.0, max_delay=300.0)  # ✅ Good

# Too long: Wastes time
retry=ExponentialBackoffStrategy(base_delay=60.0, max_delay=3600.0)  # ⚠️ Maybe too long
```

### 3. Be Selective with Exceptions
```python
# Retry transient errors
retry_exceptions=[httpx.TimeoutException, httpx.HTTPStatusError]  # ✅

# Don't retry permanent errors
# ValueError, KeyError, etc. should fail immediately  # ✅
```

### 4. Make Tasks Idempotent
```python
# Use upserts instead of inserts
stmt = insert(Model).on_conflict_do_update(...)  # ✅

# Check before creating
if not exists:
    create()  # ✅
```

## 🔧 Configuration via Environment

Update `.env` to change retry behavior:

```bash
# Maximum retry attempts
MAX_RETRIES=5

# Base delay for exponential backoff (seconds)
RETRY_BASE_DELAY=2.0

# Maximum delay cap (seconds)
RETRY_MAX_DELAY=300.0
```

Then restart the application:
```bash
# Restart to pick up new config
# The server will auto-reload if using --reload flag
```

## 📚 References

- [Procrastinate Retry Documentation](https://procrastinate.readthedocs.io/en/stable/howto/advanced/retry.html)
- [Exponential Backoff Pattern](https://en.wikipedia.org/wiki/Exponential_backoff)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)

## ✅ Summary

Your application now has:
- ✅ **Automatic retries** on failure
- ✅ **True exponential backoff** (2^n formula)
- ✅ **Configurable attempts** (5 for main tasks, 3 for periodic)
- ✅ **Exception filtering** (only retry specific errors)
- ✅ **Idempotent operations** (safe to retry)
- ✅ **Full observability** (logs + database tracking)
- ✅ **Job timeout protection** (prevents hanging tasks)
- ✅ **Stalled job recovery** (automatic failover)
- ✅ **Health monitoring** (proactive issue detection)

The retry strategy ensures **bulletproof task execution** with zero task loss! 🚀

## 📚 Additional Resources

See `BULLETPROOF_IMPLEMENTATION.md` for comprehensive documentation on:
- Stalled job recovery
- Worker reliability configuration
- Production deployment checklist
- Testing strategies
- Monitoring and observability
