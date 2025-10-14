# Architecture Overview

## System Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  (Browser, curl, API clients)                                   │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/REST
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Endpoints  │  │   Lifespan   │  │   Schemas    │         │
│  │   /tasks/*   │  │   Manager    │  │  (Pydantic)  │         │
│  │   /jobs/*    │  │              │  │              │         │
│  │   /jokes/*   │  │              │  │              │         │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘         │
│         │                  │                                     │
│         ▼                  ▼                                     │
│  ┌──────────────────────────────────────────────────┐          │
│  │         Procrastinate App (Task Queue)           │          │
│  │  - Job Submission                                │          │
│  │  - Worker Management                             │          │
│  │  - Retry Logic                                   │          │
│  └──────────────────┬───────────────────────────────┘          │
└─────────────────────┼──────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL Database                           │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ Procrastinate    │  │ Application      │                    │
│  │ Tables:          │  │ Tables:          │                    │
│  │ - jobs           │  │ - chuck_norris   │                    │
│  │ - events         │  │   _jokes         │                    │
│  │ - periodic_tasks │  │                  │                    │
│  └──────────────────┘  └──────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
                      ▲
                      │
┌─────────────────────┴───────────────────────────────────────────┐
│                    Background Worker                             │
│  ┌──────────────────────────────────────────────────┐          │
│  │  Task Execution:                                 │          │
│  │  - Fetch from queue                              │          │
│  │  - Execute with retry                            │          │
│  │  - Update status                                 │          │
│  └──────────────────────────────────────────────────┘          │
│                                                                  │
│  ┌──────────────────────────────────────────────────┐          │
│  │  Periodic Tasks:                                 │          │
│  │  - Scheduled fetch (every 2 min)                 │          │
│  │  - Stalled job retry (every 10 min)              │          │
│  └──────────────────────────────────────────────────┘          │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP
                           ▼
                  ┌─────────────────┐
                  │  Chuck Norris   │
                  │      API        │
                  │  (External)     │
                  └─────────────────┘
```

## Component Details

### 1. FastAPI Application (`app/main.py`)

**Responsibilities**:
- HTTP request handling
- Job submission to queue
- API endpoint management
- Lifespan management (startup/shutdown)
- Worker lifecycle control

**Key Features**:
- Async/await throughout
- Dependency injection for database sessions
- Automatic API documentation (Swagger/OpenAPI)
- Graceful shutdown handling

**Endpoints**:
- `POST /tasks/fetch-joke` - Submit new job
- `GET /jobs/{job_id}` - Check job status
- `GET /jokes` - List cached jokes
- `GET /jokes/{joke_id}` - Get specific joke
- `GET /stats` - System statistics
- `GET /health` - Health check

### 2. Procrastinate Task Queue (`app/procrastinate_app.py`, `app/tasks.py`)

**Responsibilities**:
- Task definition and registration
- Job queuing and scheduling
- Retry strategy management
- Worker coordination

**Task Types**:

1. **On-Demand Tasks**:
   - `fetch_and_cache_joke` - Fetch joke from API and cache

2. **Periodic Tasks**:
   - `scheduled_fetch_random_joke` - Auto-fetch every 2 minutes
   - `retry_stalled_jobs` - Recover crashed jobs every 10 minutes

**Retry Strategy**:
```python
Attempt 1: Immediate
Attempt 2: 2 seconds  (2^1 * 1s)
Attempt 3: 4 seconds  (2^2 * 1s)
Attempt 4: 8 seconds  (2^3 * 1s)
Attempt 5: 16 seconds (2^4 * 1s)
Max: 300 seconds (5 minutes)
```

### 3. Database Layer (`app/database.py`, `app/models.py`)

**Technologies**:
- SQLAlchemy 2.0 (async)
- asyncpg driver
- PostgreSQL 16

**Models**:

1. **ChuckNorrisJoke**:
   - Stores cached API responses
   - Indexed for fast queries
   - Timestamps for cache management

2. **Procrastinate Tables** (auto-created):
   - `procrastinate_jobs` - Job queue and status
   - `procrastinate_events` - Job execution history
   - `procrastinate_periodic_defers` - Periodic task tracking

**Connection Pooling**:
- Pool size: 10 connections
- Max overflow: 20 connections
- Pre-ping enabled for connection health checks

### 4. Configuration (`app/config.py`)

**Settings Management**:
- Pydantic-based validation
- Environment variable loading
- Type safety
- Default values

**Key Settings**:
- Database URLs
- API endpoints
- Retry configuration
- Worker settings

## Data Flow

### Job Submission Flow

```
1. Client Request
   POST /tasks/fetch-joke
   {"category": "dev"}
   
2. FastAPI Endpoint
   - Validate request (Pydantic)
   - Call task.defer_async()
   
3. Procrastinate
   - Insert job into database
   - Return job ID
   
4. Response to Client
   {"job_id": 123, "status": "queued"}
   
5. Worker (Background)
   - Poll database for jobs
   - Pick up job 123
   - Execute task
   
6. Task Execution
   - Fetch from API
   - Cache in database
   - Update job status
```

### Retry Flow

```
1. Task Fails
   - Exception raised
   - Caught by Procrastinate
   
2. Retry Decision
   - Check attempts < max_retries
   - Calculate backoff delay
   
3. Reschedule
   - Update job status to "todo"
   - Set scheduled_at = now + delay
   - Increment attempts
   
4. Worker Picks Up Again
   - After delay expires
   - Retry execution
   
5. Success or Final Failure
   - Success: status = "succeeded"
   - Max retries: status = "failed"
```

### Crash Recovery Flow

```
1. Application Crashes
   - Worker stops mid-execution
   - Jobs left in "doing" status
   
2. Periodic Task Runs (every 10 min)
   - Query for stalled jobs
   - Jobs in "doing" status for > timeout
   
3. Retry Stalled Jobs
   - Reset status to "todo"
   - Reschedule immediately
   
4. Worker Picks Up
   - Execute as normal
   - Complete successfully
```

## Bulletproof Features

### 1. Idempotent Operations

**Database Upsert**:
```python
stmt = insert(ChuckNorrisJoke).values(...)
stmt = stmt.on_conflict_do_update(
    index_elements=["joke_id"],
    set_={...}
)
```

**Benefits**:
- Safe to retry without duplicates
- No data corruption on retry
- Consistent state

### 2. Exponential Backoff

**Implementation**:
```python
delay = min(
    base_delay * (2 ** attempt),
    max_delay
)
```

**Benefits**:
- Reduces load on failing services
- Increases success probability
- Prevents thundering herd

### 3. Stalled Job Recovery

**Detection**:
- Jobs in "doing" status
- Last updated > timeout threshold
- Worker no longer active

**Recovery**:
- Automatic retry
- No manual intervention
- Guaranteed completion

### 4. Graceful Shutdown

**Process**:
1. Receive shutdown signal
2. Stop accepting new jobs
3. Wait for current jobs (timeout: 30s)
4. Cancel remaining jobs
5. Close connections

**Benefits**:
- No job loss
- Clean state
- Fast restart

## Scalability

### Horizontal Scaling

**Multiple Workers**:
```bash
# Terminal 1
python scripts/run_worker.py

# Terminal 2
python scripts/run_worker.py

# Terminal 3
python scripts/run_worker.py
```

**Benefits**:
- Increased throughput
- Load distribution
- Fault tolerance

### Queue Separation

**Different Queues**:
```python
@app.task(queue="high_priority")
async def urgent_task():
    ...

@app.task(queue="low_priority")
async def background_task():
    ...
```

**Worker Assignment**:
```python
# High-priority worker
app.run_worker_async(queues=["high_priority"])

# Low-priority worker
app.run_worker_async(queues=["low_priority"])
```

### Database Optimization

**Indexes**:
- `joke_id` - Unique constraint + index
- `category` - Filter queries
- `(category, created_at)` - Composite index

**Connection Pooling**:
- Reuse connections
- Reduce overhead
- Handle spikes

## Monitoring

### Key Metrics

1. **Job Metrics**:
   - Jobs queued
   - Jobs succeeded
   - Jobs failed
   - Average execution time
   - Retry rate

2. **System Metrics**:
   - Worker count
   - Queue depth
   - Database connections
   - API response time

3. **Business Metrics**:
   - Jokes cached
   - API calls made
   - Cache hit rate

### Monitoring Tools

1. **pgAdmin**:
   - Visual database inspection
   - Query execution
   - Performance analysis

2. **Application Logs**:
   - Structured logging
   - Error tracking
   - Execution traces

3. **Database Queries**:
   ```sql
   -- Job status distribution
   SELECT status, COUNT(*) 
   FROM procrastinate_jobs 
   GROUP BY status;
   
   -- Failed jobs
   SELECT * FROM procrastinate_jobs 
   WHERE status = 'failed' 
   ORDER BY scheduled_at DESC;
   
   -- Average execution time
   SELECT AVG(EXTRACT(EPOCH FROM (finished_at - started_at))) 
   FROM procrastinate_jobs 
   WHERE status = 'succeeded';
   ```

## Security Considerations

### Current Implementation

1. **Database Credentials**:
   - Stored in `.env` file
   - Not committed to git
   - Used via environment variables

2. **API Access**:
   - No authentication (demo)
   - Public endpoints
   - Rate limiting not implemented

### Production Recommendations

1. **Authentication**:
   - Add JWT tokens
   - API key validation
   - OAuth2 integration

2. **Authorization**:
   - Role-based access control
   - Job ownership
   - Resource isolation

3. **Secrets Management**:
   - Use secrets manager (AWS Secrets Manager, Vault)
   - Rotate credentials
   - Encrypt at rest

4. **Network Security**:
   - HTTPS only
   - VPC isolation
   - Firewall rules

## Performance Characteristics

### Throughput

**Single Worker**:
- ~10-20 jobs/second (I/O bound)
- Depends on API latency
- Database write speed

**Multiple Workers**:
- Linear scaling up to database limits
- ~100+ jobs/second with 10 workers

### Latency

**Job Submission**:
- < 10ms (database insert)
- Async, non-blocking

**Job Execution**:
- 100-500ms (API call)
- Variable based on external API

**Retry Delay**:
- 2s to 300s (exponential backoff)
- Configurable

### Resource Usage

**Memory**:
- ~50-100MB per worker
- Depends on concurrency

**CPU**:
- Low (mostly I/O wait)
- Spikes during JSON parsing

**Database**:
- ~10-20 connections per worker
- Moderate disk I/O

## Future Enhancements

### Short Term

1. **Metrics Dashboard**:
   - Prometheus integration
   - Grafana dashboards
   - Real-time monitoring

2. **Enhanced Logging**:
   - Structured logging (JSON)
   - Log aggregation (ELK stack)
   - Distributed tracing

3. **Testing**:
   - Unit tests
   - Integration tests
   - Load tests

### Long Term

1. **Advanced Features**:
   - Job priorities
   - Job dependencies
   - Batch processing
   - Dead letter queue

2. **Observability**:
   - OpenTelemetry integration
   - APM (Application Performance Monitoring)
   - Error tracking (Sentry)

3. **Deployment**:
   - Kubernetes manifests
   - Helm charts
   - CI/CD pipeline
   - Auto-scaling

## Conclusion

This architecture provides:

- ✅ **Reliability**: Automatic retries and crash recovery
- ✅ **Scalability**: Horizontal scaling of workers
- ✅ **Maintainability**: Clean code structure and documentation
- ✅ **Observability**: Comprehensive logging and monitoring
- ✅ **Performance**: Efficient async operations and connection pooling

The system is production-ready for moderate loads and can be enhanced for high-scale deployments.
