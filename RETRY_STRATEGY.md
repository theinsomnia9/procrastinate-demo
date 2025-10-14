# Exponential Backoff Retry Strategy

## 📊 Overview

This application implements **exponential backoff** retry strategies using Procrastinate's built-in `RetryStrategy` class. All tasks automatically retry on failure with increasing delays.

## 🎯 Configuration

### Main Task: `fetch_and_cache_joke`

```python
@app.task(
    queue="api_calls",
    retry=RetryStrategy(
        max_attempts=5,              # Total attempts (1 initial + 4 retries)
        wait=2.0,                    # Base delay: 2 seconds
        retry_exceptions=[           # Only retry these exceptions
            TaskError,
            httpx.HTTPError,
            httpx.TimeoutException
        ],
    ),
    pass_context=True,
)
```

**Retry Schedule:**
- Attempt 1: Immediate (0s)
- Attempt 2: After 2 seconds
- Attempt 3: After 4 seconds (2 × 2)
- Attempt 4: After 8 seconds (2 × 4)
- Attempt 5: After 16 seconds (2 × 8)

**Total time before giving up:** ~30 seconds

### Periodic Tasks

**`scheduled_fetch_random_joke`** (runs every 2 minutes):
```python
retry=RetryStrategy(max_attempts=3, wait=2.0)
```
- 3 total attempts with 2s base delay
- Retries: 0s → 2s → 4s

**`retry_stalled_jobs`** (runs every 10 minutes):
```python
retry=RetryStrategy(max_attempts=3, wait=5.0)
```
- 3 total attempts with 5s base delay
- Retries: 0s → 5s → 10s

## 🔢 How Exponential Backoff Works

Procrastinate's default retry strategy uses **linear backoff** with the `wait` parameter:

```
delay = wait × attempt_number
```

### Example for `fetch_and_cache_joke`:

| Attempt | Calculation | Delay | Cumulative Time |
|---------|-------------|-------|-----------------|
| 1       | -           | 0s    | 0s              |
| 2       | 2.0 × 1     | 2s    | 2s              |
| 3       | 2.0 × 2     | 4s    | 6s              |
| 4       | 2.0 × 3     | 6s    | 12s             |
| 5       | 2.0 × 4     | 8s    | 20s             |

**Note:** Procrastinate 3.x uses linear backoff by default. For true exponential backoff (2^n), you would need a custom retry strategy.

## 🎨 Custom Exponential Backoff (Optional)

If you want true exponential backoff (2^n), you can create a custom retry strategy:

```python
from procrastinate.retry import BaseRetryStrategy

class ExponentialBackoffStrategy(BaseRetryStrategy):
    def __init__(self, max_attempts: int = 5, base_delay: float = 2.0, max_delay: float = 300.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def get_schedule_in(self, attempts: int) -> dict | None:
        if attempts >= self.max_attempts:
            return None  # Stop retrying
        
        # Exponential: base_delay × (2 ^ attempts)
        delay = min(self.base_delay * (2 ** attempts), self.max_delay)
        return {"seconds": int(delay)}

# Use it:
@app.task(
    retry=ExponentialBackoffStrategy(max_attempts=5, base_delay=2.0, max_delay=300.0)
)
async def my_task():
    ...
```

**True Exponential Schedule:**
- Attempt 1: 0s
- Attempt 2: 2s (2 × 2^0)
- Attempt 3: 4s (2 × 2^1)
- Attempt 4: 8s (2 × 2^2)
- Attempt 5: 16s (2 × 2^3)
- Attempt 6: 32s (2 × 2^4)

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
- ✅ Reduces load on failing services (delays between retries)
- ✅ Increases success rate without manual intervention
- ✅ Prevents thundering herd problem

### Considerations
- ⚠️ Failed jobs take longer to complete (up to 30s for 5 attempts)
- ⚠️ Database stores retry history (more rows in events table)
- ⚠️ Worker capacity used during retry delays

## 🎯 Best Practices

### 1. Choose Appropriate Max Attempts
```python
# Quick operations (< 1s)
retry=RetryStrategy(max_attempts=3, wait=1.0)

# Medium operations (1-5s)
retry=RetryStrategy(max_attempts=5, wait=2.0)

# Long operations (> 5s)
retry=RetryStrategy(max_attempts=3, wait=5.0)
```

### 2. Set Reasonable Delays
```python
# Too short: Hammers failing service
retry=RetryStrategy(wait=0.1)  # ❌ Bad

# Good: Gives service time to recover
retry=RetryStrategy(wait=2.0)  # ✅ Good

# Too long: Wastes time
retry=RetryStrategy(wait=60.0)  # ⚠️ Maybe too long
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
- ✅ **Linear backoff** (Procrastinate default)
- ✅ **Configurable attempts** (5 for main tasks, 3 for periodic)
- ✅ **Exception filtering** (only retry specific errors)
- ✅ **Idempotent operations** (safe to retry)
- ✅ **Full observability** (logs + database tracking)

The retry strategy ensures **bulletproof task execution** even when external services are temporarily unavailable! 🚀
