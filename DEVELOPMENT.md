# Development Guide

## Development Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git
- Make (optional, for convenience commands)

### Initial Setup

```bash
# Clone the repository
cd /home/homie/projects/procrastinate-demo

# Run the quick start script
chmod +x start.sh
./start.sh

# Or use Make
make start
make install
make db-init
```

## Development Workflow

### Running the Application

#### Option 1: All-in-One (Recommended for Development)

Run FastAPI with embedded worker:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

This starts both the API server and the background worker in a single process.

#### Option 2: Separate Processes (Recommended for Production)

Terminal 1 - API Server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --no-worker
```

Terminal 2 - Worker:
```bash
python scripts/run_worker.py
```

This allows independent scaling and monitoring.

### Testing Changes

1. **Test Task Submission**:
   ```bash
   python scripts/test_task.py 5
   ```

2. **Monitor Logs**:
   - Application logs in terminal
   - Docker logs: `docker-compose logs -f postgres`

3. **Check Database**:
   - pgAdmin: http://localhost:5050
   - Or use psql:
     ```bash
     docker exec -it procrastinate_postgres psql -U procrastinate -d procrastinate_db
     ```

### Code Structure

```
app/
├── main.py              # FastAPI app, endpoints, lifespan management
├── config.py            # Configuration and settings
├── database.py          # SQLAlchemy setup and session management
├── models.py            # Database models
├── schemas.py           # Pydantic schemas for API
├── tasks.py             # Procrastinate task definitions
└── procrastinate_app.py # Procrastinate configuration
```

## Adding New Tasks

### 1. Define the Task

Edit `app/tasks.py`:

```python
@app.task(
    queue="my_queue",
    retry=5,
    pass_context=True,
)
async def my_new_task(context, param1: str, param2: int):
    """
    Task description.
    
    Args:
        context: Procrastinate job context
        param1: Description
        param2: Description
    """
    attempt = context.job.attempts
    logger.info(f"Running my_new_task (attempt {attempt})")
    
    try:
        # Your task logic here
        result = await some_async_operation(param1, param2)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise
```

### 2. Add API Endpoint

Edit `app/main.py`:

```python
@app.post("/tasks/my-task")
async def trigger_my_task(param1: str, param2: int):
    """Trigger my new task."""
    job = await my_new_task.defer_async(param1=param1, param2=param2)
    return {"job_id": job.id, "status": "queued"}
```

### 3. Test the Task

```python
# In scripts/test_task.py or create a new test script
from app.tasks import my_new_task

async with procrastinate_app.open_async():
    job = await my_new_task.defer_async(param1="test", param2=42)
    print(f"Submitted job {job.id}")
```

## Adding New Models

### 1. Create Model

Edit `app/models.py`:

```python
class MyNewModel(Base):
    __tablename__ = "my_table"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### 2. Create Schema

Edit `app/schemas.py`:

```python
class MyNewModelResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    
    class Config:
        from_attributes = True
```

### 3. Add Migration (Optional)

For production, use Alembic:

```bash
# Initialize Alembic (first time only)
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Add my_table"

# Apply migration
alembic upgrade head
```

## Debugging

### Enable Debug Logging

Edit `app/main.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

### Debug Task Execution

Add breakpoints or logging in `app/tasks.py`:

```python
@app.task(...)
async def my_task(context, ...):
    import pdb; pdb.set_trace()  # Debugger
    # or
    logger.debug(f"Debug info: {context.job}")
```

### Inspect Job Queue

```sql
-- Connect to database
docker exec -it procrastinate_postgres psql -U procrastinate -d procrastinate_db

-- View all jobs
SELECT id, task_name, status, attempts, scheduled_at 
FROM procrastinate_jobs 
ORDER BY id DESC 
LIMIT 10;

-- View job details
SELECT * FROM procrastinate_jobs WHERE id = 1;

-- View job events
SELECT * FROM procrastinate_events WHERE job_id = 1 ORDER BY at DESC;
```

## Performance Tuning

### Worker Configuration

Adjust worker settings in `app/main.py`:

```python
await procrastinate_app.run_worker_async(
    queues=["api_calls", "default"],
    concurrency=10,  # Number of concurrent tasks
    wait=True,
)
```

### Database Connection Pool

Edit `app/database.py`:

```python
engine = create_async_engine(
    settings.database_url,
    pool_size=20,        # Increase pool size
    max_overflow=40,     # Increase overflow
    pool_pre_ping=True,
)
```

### Retry Strategy

Edit `app/config.py`:

```python
class Settings(BaseSettings):
    max_retries: int = 10              # More retries
    retry_base_delay: float = 1.0      # Faster initial retry
    retry_max_delay: float = 600.0     # Longer max delay
```

## Testing

### Unit Tests

Create `tests/test_tasks.py`:

```python
import pytest
from procrastinate import testing
from app.tasks import fetch_and_cache_joke
from app.procrastinate_app import app

@pytest.fixture
def in_memory_app():
    connector = testing.InMemoryConnector()
    with app.replace_connector(connector) as test_app:
        yield test_app

@pytest.mark.asyncio
async def test_fetch_joke(in_memory_app):
    # Defer task
    await fetch_and_cache_joke.defer_async(category="dev")
    
    # Check job was created
    assert len(in_memory_app.connector.jobs) == 1
    
    # Run worker
    in_memory_app.run_worker(wait=False)
```

### Integration Tests

Create `tests/test_api.py`:

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_trigger_task():
    response = client.post("/tasks/fetch-joke", json={})
    assert response.status_code == 200
    assert "job_id" in response.json()
```

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/ -v
```

## Common Issues

### Issue: Database Connection Failed

**Solution**:
```bash
# Check if PostgreSQL is running
docker-compose ps

# Restart PostgreSQL
docker-compose restart postgres

# Check logs
docker-compose logs postgres
```

### Issue: Worker Not Processing Jobs

**Solution**:
```bash
# Check worker logs
# Look for "Procrastinate worker started"

# Verify queues
# In pgAdmin, check procrastinate_jobs table

# Restart worker
# Ctrl+C and restart uvicorn
```

### Issue: Port Already in Use

**Solution**:
```bash
# Use different port
uvicorn app.main:app --reload --port 8001

# Or kill existing process
lsof -ti:8000 | xargs kill -9
```

## Best Practices

### 1. Task Design

- ✅ Keep tasks idempotent
- ✅ Use database transactions
- ✅ Handle all exceptions
- ✅ Log important events
- ✅ Return structured results

### 2. Error Handling

```python
@app.task(retry=5)
async def my_task(context):
    try:
        result = await risky_operation()
        return {"status": "success", "result": result}
    except SpecificError as e:
        logger.error(f"Specific error: {e}")
        raise  # Will retry
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise
```

### 3. Database Operations

```python
# Use async context manager
async with AsyncSessionLocal() as session:
    try:
        # Your operations
        await session.commit()
    except Exception:
        await session.rollback()
        raise
```

### 4. Configuration

- ✅ Use environment variables
- ✅ Validate settings with Pydantic
- ✅ Use different configs for dev/prod
- ✅ Never commit secrets

## Deployment

### Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t procrastinate-demo .
docker run -p 8000:8000 --env-file .env procrastinate-demo
```

### Production Checklist

- [ ] Use production database (not localhost)
- [ ] Set up proper logging (e.g., to file or service)
- [ ] Configure monitoring (Prometheus, Grafana)
- [ ] Set up alerts for failed jobs
- [ ] Use secrets management (not .env files)
- [ ] Enable HTTPS
- [ ] Set up backup strategy
- [ ] Configure auto-scaling for workers
- [ ] Add health checks
- [ ] Set up CI/CD pipeline

## Resources

- [Procrastinate Docs](https://procrastinate.readthedocs.io/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)
