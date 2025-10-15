# 🛡️ Bulletproof Procrastinate Implementation

## Overview

This document describes the bulletproof task queue implementation using the latest Procrastinate features. The system ensures **zero task loss** through exponential retry, automatic failover, and comprehensive monitoring.

## 🎯 Key Features

### 1. True Exponential Backoff Retry Strategy

**Implementation**: Custom `ExponentialBackoffStrategy` class based on Procrastinate's `BaseRetryStrategy`

**Formula**: `delay = min(base_delay × 2^attempts, max_delay)`

**Benefits**:
- Prevents thundering herd problem
- Gives failing services time to recover
- Configurable per-task retry behavior
- Exception-specific retry logic

**Example Schedule** (base_delay=2s, max_delay=300s):
```
Attempt 1: Immediate (0s)
Attempt 2: 2s  (2 × 2^0)
Attempt 3: 4s  (2 × 2^1)
Attempt 4: 8s  (2 × 2^2)
Attempt 5: 16s (2 × 2^3)
Attempt 6: 32s (2 × 2^4)
...
Max: 300s (5 minutes)
```

### 2. Job Timeout Protection

**Implementation**: `asyncio.timeout()` wrapper around task execution

**Configuration**: `JOB_TIMEOUT=300` (5 minutes)

**Behavior**:
- Tasks exceeding timeout are automatically cancelled
- Timeout triggers retry with exponential backoff
- Prevents indefinite task execution
- Protects against hanging operations

### 3. Automatic Stalled Job Recovery

**Implementation**: Periodic task `retry_stalled_jobs` runs every 10 minutes

**Detection Criteria**:
- Job status is 'doing' (being processed)
- Worker that picked up the job is no longer active
- Job hasn't been updated recently

**Recovery Process**:
1. Detect stalled jobs via `app.job_manager.get_stalled_jobs()`
2. Retry each stalled job via `app.job_manager.retry_job(job)`
3. Log detailed recovery metrics
4. Continue until all stalled jobs are recovered

**Guarantees**:
- ✅ No tasks are lost due to worker crashes
- ✅ No tasks are lost due to network failures
- ✅ No tasks are lost due to system restarts
- ✅ All tasks eventually complete or fail explicitly

### 4. Worker Reliability Configuration

**Optimal Settings**:
```python
procrastinate_app.run_worker_async(
    queues=["api_calls", "default"],
    concurrency=10,              # Handle 10 jobs concurrently
    wait=True,                   # Keep worker alive even when queue is empty
    listen_notify=True,          # Real-time job notifications (low latency)
    delete_jobs="never",         # Preserve job history for debugging
)
```

**Connection Pooling**:
```python
connector=procrastinate.PsycopgConnector(
    conninfo=settings.procrastinate_database_url,
    maxsize=20,  # Connection pool size
)
```

### 5. Graceful Shutdown

**Implementation**: Proper cleanup on application shutdown

**Process**:
1. Cancel worker task
2. Wait up to `WORKER_TIMEOUT` seconds for jobs to complete
3. Log shutdown status
4. Jobs exceeding timeout are marked as stalled
5. Stalled jobs are automatically retried on next worker start

### 6. Health Monitoring

**Implementation**: Periodic `health_check_task` runs every 5 minutes

**Checks**:
- Database connectivity
- Worker status
- System metrics

**Benefits**:
- Early detection of issues
- Proactive alerting (can be extended)
- System health visibility

## 📊 Task Configuration Matrix

| Task | Queue | Max Attempts | Base Delay | Max Delay | Timeout | Queueing Lock |
|------|-------|--------------|------------|-----------|---------|---------------|
| `fetch_and_cache_joke` | api_calls | 5 | 2s | 300s | 300s | No |
| `scheduled_fetch_random_joke` | default | 3 | 2s | 60s | N/A | Yes |
| `retry_stalled_jobs` | default | 3 | 5s | 60s | N/A | Yes |
| `health_check_task` | default | 2 | 10s | 30s | N/A | Yes |

## 🔧 Configuration

### Environment Variables

```bash
# Retry Strategy
MAX_RETRIES=5                    # Maximum retry attempts per task
RETRY_BASE_DELAY=2.0            # Base delay in seconds
RETRY_MAX_DELAY=300.0           # Maximum delay cap (5 minutes)

# Job Timeout
JOB_TIMEOUT=300                 # Maximum job execution time (5 minutes)

# Worker Settings
WORKER_CONCURRENCY=10           # Concurrent jobs per worker
WORKER_TIMEOUT=30               # Graceful shutdown timeout

# Stalled Job Detection
STALLED_JOB_CHECK_INTERVAL=10   # Check every 10 minutes
STALLED_JOB_THRESHOLD=600       # Consider stalled after 10 minutes
```

### Task-Level Configuration

```python
@app.task(
    queue="api_calls",
    retry=ExponentialBackoffStrategy(
        max_attempts=5,
        base_delay=2.0,
        max_delay=300.0,
        retry_exceptions=[TaskError, httpx.HTTPError, httpx.TimeoutException],
    ),
    pass_context=True,
)
async def my_task(context, **kwargs):
    # Wrap with timeout
    async with asyncio.timeout(settings.job_timeout):
        # Task implementation
        pass
```

## 🛡️ Bulletproof Guarantees

### 1. No Task Loss on Worker Crash

**Scenario**: Worker process crashes while processing jobs

**Protection**:
- Jobs in 'doing' status are detected as stalled
- `retry_stalled_jobs` automatically retries them
- Maximum detection latency: 10 minutes

**Test**:
```bash
# Submit jobs
curl -X POST http://localhost:8000/tasks/fetch-joke

# Kill worker (Ctrl+C)
# Wait 10 minutes
# Restart worker

# Result: All jobs are automatically retried
```

### 2. No Task Loss on Network Failure

**Scenario**: External API or database becomes temporarily unavailable

**Protection**:
- Exponential backoff retry strategy
- Up to 5 retry attempts
- Total retry window: ~30 seconds
- Idempotent operations prevent duplicates

**Test**:
```bash
# Disconnect network
# Submit job
# Observe retries in logs
# Reconnect network
# Result: Job eventually succeeds
```

### 3. No Task Loss on System Restart

**Scenario**: Server restarts or application redeployment

**Protection**:
- Jobs persisted in PostgreSQL
- Worker picks up pending jobs on startup
- Stalled jobs detected and retried
- No in-memory state required

**Test**:
```bash
# Submit jobs
docker-compose restart
# Result: All jobs resume processing
```

### 4. No Task Loss on Database Failure

**Scenario**: PostgreSQL connection temporarily lost

**Protection**:
- Connection pooling with automatic reconnection
- Database errors trigger task retry
- Worker continues processing after reconnection

### 5. No Duplicate Task Execution

**Scenario**: Task is retried but original execution succeeds

**Protection**:
- Idempotent operations using `INSERT ... ON CONFLICT DO UPDATE`
- Queueing locks prevent duplicate periodic tasks
- Database constraints enforce uniqueness

## 📈 Monitoring and Observability

### Database Queries

**View All Jobs**:
```sql
SELECT 
    id, 
    task_name, 
    status, 
    attempts, 
    scheduled_at,
    started_at,
    queue_name
FROM procrastinate_jobs
ORDER BY scheduled_at DESC
LIMIT 100;
```

**Count Jobs by Status**:
```sql
SELECT 
    status, 
    COUNT(*) as count
FROM procrastinate_jobs
GROUP BY status;
```

**Find Failed Jobs**:
```sql
SELECT 
    id,
    task_name,
    attempts,
    scheduled_at,
    started_at
FROM procrastinate_jobs
WHERE status = 'failed'
ORDER BY scheduled_at DESC;
```

**Find Stalled Jobs** (manual check):
```sql
SELECT 
    j.id,
    j.task_name,
    j.status,
    j.attempts,
    j.started_at,
    NOW() - j.started_at as running_duration
FROM procrastinate_jobs j
WHERE j.status = 'doing'
    AND NOW() - j.started_at > INTERVAL '10 minutes'
ORDER BY j.started_at;
```

**View Retry Events**:
```sql
SELECT 
    job_id,
    type,
    at,
    attempts
FROM procrastinate_events
WHERE type = 'deferred_for_retry'
ORDER BY at DESC
LIMIT 50;
```

### API Endpoints

**Check Job Status**:
```bash
curl http://localhost:8000/jobs/{job_id}
```

**System Health**:
```bash
curl http://localhost:8000/health
```

**Statistics**:
```bash
curl http://localhost:8000/stats
```

### Log Monitoring

**Key Log Patterns**:
```
# Job execution
Job {id}: Fetching joke (attempt {n}/{max})

# Successful completion
Job {id}: Successfully cached joke

# Retry triggered
Job {id}: API timeout on attempt {n}

# Stalled job detection
Found {n} stalled jobs, retrying...

# Stalled job recovery
Successfully retried stalled job {id}

# Health check
Health check passed: Database connection OK
```

## 🧪 Testing Bulletproof Features

### Test 1: Exponential Backoff

```bash
# Temporarily break API URL in .env
API_BASE_URL=https://invalid-api-url.com

# Submit task
curl -X POST http://localhost:8000/tasks/fetch-joke

# Observe logs - you'll see:
# Attempt 1: Immediate
# Attempt 2: After 2s
# Attempt 3: After 4s
# Attempt 4: After 8s
# Attempt 5: After 16s

# Restore API URL
API_BASE_URL=https://api.chucknorris.io

# Task should eventually succeed
```

### Test 2: Job Timeout

```python
# In tasks.py, reduce timeout temporarily
async with asyncio.timeout(5):  # 5 seconds instead of 300

# Submit task that takes longer
# Observe timeout and retry
```

### Test 3: Stalled Job Recovery

```bash
# Submit multiple jobs
for i in {1..10}; do
    curl -X POST http://localhost:8000/tasks/fetch-joke
done

# Kill application (Ctrl+C) while jobs are processing

# Wait 10 minutes (or adjust cron for testing)

# Restart application
uvicorn app.main:app --reload

# Check logs - stalled jobs should be detected and retried
```

### Test 4: Worker Crash Recovery

```bash
# Start application
uvicorn app.main:app --reload

# Submit jobs
curl -X POST http://localhost:8000/tasks/fetch-joke

# Force kill worker process
kill -9 $(pgrep -f uvicorn)

# Restart
uvicorn app.main:app --reload

# All jobs should resume
```

### Test 5: Idempotency

```bash
# Submit same joke multiple times
for i in {1..5}; do
    curl -X POST http://localhost:8000/tasks/fetch-joke \
        -H "Content-Type: application/json" \
        -d '{"category": "dev"}'
done

# Check database - no duplicate jokes
psql -U procrastinate -d procrastinate_db \
    -c "SELECT joke_id, COUNT(*) FROM chuck_norris_jokes GROUP BY joke_id HAVING COUNT(*) > 1;"

# Result: No duplicates
```

## 🚀 Production Deployment Checklist

- [ ] Set appropriate `MAX_RETRIES` based on task criticality
- [ ] Configure `JOB_TIMEOUT` based on expected task duration
- [ ] Set `WORKER_CONCURRENCY` based on available resources
- [ ] Enable connection pooling with appropriate `maxsize`
- [ ] Set `delete_jobs="never"` for debugging (or "successful" for production)
- [ ] Configure monitoring and alerting for failed jobs
- [ ] Set up log aggregation (e.g., ELK, Datadog)
- [ ] Configure database backups
- [ ] Test stalled job recovery in staging
- [ ] Document task retry behavior for operations team
- [ ] Set up health check monitoring
- [ ] Configure alerts for stalled job detection

## 📚 References

- [Procrastinate Documentation](https://procrastinate.readthedocs.io/)
- [Retry Strategy Documentation](https://procrastinate.readthedocs.io/en/stable/howto/advanced/retry.html)
- [Stalled Jobs Documentation](https://procrastinate.readthedocs.io/en/stable/howto/production/retry_stalled_jobs.html)
- [Worker Configuration](https://procrastinate.readthedocs.io/en/stable/howto/basics/worker.html)

## 🎓 Architecture Decisions

### Why Exponential Backoff?

- **Linear backoff** (default): Simple but can overwhelm failing services
- **Exponential backoff**: Gives services time to recover, prevents thundering herd
- **With max delay cap**: Prevents excessive wait times

### Why Keep Job History?

- Debugging failed jobs
- Analyzing retry patterns
- Compliance and audit trails
- Performance monitoring

### Why Periodic Stalled Job Detection?

- Worker crashes don't lose tasks
- Network partitions are handled
- System restarts are seamless
- No manual intervention required

### Why Job Timeouts?

- Prevents resource exhaustion
- Detects hanging operations
- Enables faster failure detection
- Improves system predictability

## ✅ Summary

This implementation provides **bulletproof task execution** with:

1. ✅ **True exponential backoff** - Optimal retry strategy
2. ✅ **Job timeout protection** - No hanging tasks
3. ✅ **Automatic stalled job recovery** - Zero task loss
4. ✅ **Worker reliability** - Optimal configuration
5. ✅ **Graceful shutdown** - Clean application lifecycle
6. ✅ **Health monitoring** - Proactive issue detection
7. ✅ **Idempotent operations** - Safe retries
8. ✅ **Comprehensive logging** - Full observability
9. ✅ **Production-ready** - Battle-tested patterns
10. ✅ **Zero manual intervention** - Fully automated recovery

**Result**: No tasks are missed, all tasks eventually complete or fail explicitly with full traceability.
