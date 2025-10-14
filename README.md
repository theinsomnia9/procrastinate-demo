# 🚀 Procrastinate Demo - Production-Ready Task Scheduling

A bulletproof FastAPI application demonstrating best practices for asynchronous task scheduling using [Procrastinate](https://procrastinate.readthedocs.io/) with PostgreSQL.

## ✨ Features

- **Exponential Backoff Retry Strategy**: Automatic retries with configurable exponential backoff (2s → 4s → 8s → 16s → 32s)
- **Crash Recovery**: Periodic stalled job detection and automatic retry
- **Idempotent Operations**: Safe to retry without side effects
- **Periodic Tasks**: Scheduled tasks that run automatically
- **Real-time Monitoring**: pgAdmin UI for database and job inspection
- **RESTful API**: Clean FastAPI endpoints for job management
- **Type Safety**: Full Pydantic validation and SQLAlchemy ORM
- **Production Ready**: Proper logging, error handling, and graceful shutdown

## 🏗️ Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   FastAPI   │─────▶│ Procrastinate│─────▶│ PostgreSQL  │
│   Server    │      │    Worker    │      │  Database   │
└─────────────┘      └──────────────┘      └─────────────┘
       │                     │                     │
       │                     │                     │
       ▼                     ▼                     ▼
  HTTP Requests        Task Queue           Job Storage
  Job Submission       Execution            Result Cache
```

### Components

1. **FastAPI Server**: Handles HTTP requests and job submission
2. **Procrastinate Worker**: Executes tasks asynchronously in the background
3. **PostgreSQL**: Stores job queue, results, and cached data
4. **Chuck Norris API**: External API for demonstration (free, no auth required)

## 📋 Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Git

## 🚀 Quick Start

### 1. Clone and Setup

```bash
cd /home/homie/projects/procrastinate-demo

# Copy environment variables
cp .env.example .env

# Start PostgreSQL and pgAdmin
docker-compose up -d

# Wait for PostgreSQL to be ready (about 10 seconds)
sleep 10
```

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run the Application

```bash
# Start the FastAPI server (includes worker)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The application will:
- Initialize database tables
- Apply Procrastinate schema
- Start the background worker
- Begin accepting HTTP requests

## 🎯 Usage

### Web Interface

Open your browser to:
- **API Documentation**: http://localhost:8000/docs
- **Main Page**: http://localhost:8000
- **pgAdmin**: http://localhost:5050 (login: admin@admin.com / admin)

### API Endpoints

#### 1. Trigger a Task

```bash
# Fetch a random joke
curl -X POST http://localhost:8000/tasks/fetch-joke \
  -H "Content-Type: application/json" \
  -d '{}'

# Fetch a joke from specific category
curl -X POST http://localhost:8000/tasks/fetch-joke \
  -H "Content-Type: application/json" \
  -d '{"category": "dev"}'
```

Response:
```json
{
  "job_id": 1,
  "status": "queued",
  "message": "Job 1 queued successfully. Category: random"
}
```

#### 2. Check Job Status

```bash
curl http://localhost:8000/jobs/1
```

Response:
```json
{
  "job_id": 1,
  "task_name": "app.tasks.fetch_and_cache_joke",
  "status": "succeeded",
  "attempts": 1,
  "scheduled_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:01Z",
  "queue_name": "api_calls"
}
```

#### 3. List Cached Jokes

```bash
# Get first 10 jokes
curl http://localhost:8000/jokes

# Pagination
curl "http://localhost:8000/jokes?skip=10&limit=20"

# Filter by category
curl "http://localhost:8000/jokes?category=dev"
```

#### 4. Get Statistics

```bash
curl http://localhost:8000/stats
```

Response:
```json
{
  "total_jokes": 42,
  "categories": {
    "dev": 15,
    "uncategorized": 27
  },
  "recent_jobs": 10
}
```

## 🔧 Configuration

Edit `.env` file to customize:

```bash
# Database connection
DATABASE_URL=postgresql+asyncpg://procrastinate:procrastinate@localhost:5432/procrastinate_db
PROCRASTINATE_DATABASE_URL=postgresql://procrastinate:procrastinate@localhost:5432/procrastinate_db

# API configuration
API_BASE_URL=https://api.chucknorris.io

# Retry configuration
MAX_RETRIES=5
RETRY_BASE_DELAY=2.0      # Base delay in seconds
RETRY_MAX_DELAY=300.0     # Max delay (5 minutes)
```

## 🛡️ Bulletproof Features

### 1. Exponential Backoff

Tasks automatically retry with increasing delays:
- Attempt 1: Immediate
- Attempt 2: 2 seconds
- Attempt 3: 4 seconds
- Attempt 4: 8 seconds
- Attempt 5: 16 seconds
- Max delay: 300 seconds (5 minutes)

### 2. Crash Recovery

A periodic task runs every 10 minutes to detect and retry stalled jobs:

```python
@app.periodic(cron="*/10 * * * *")
async def retry_stalled_jobs(context, timestamp: int):
    stalled_jobs = await app.job_manager.get_stalled_jobs()
    for job in stalled_jobs:
        await app.job_manager.retry_job(job)
```

### 3. Idempotent Operations

Database operations use PostgreSQL's `INSERT ... ON CONFLICT DO UPDATE` to ensure tasks can be safely retried:

```python
stmt = insert(ChuckNorrisJoke).values(...)
stmt = stmt.on_conflict_do_update(
    index_elements=["joke_id"],
    set_={...}
)
```

### 4. Graceful Shutdown

The application handles shutdown gracefully:
- Cancels the worker task
- Waits up to 30 seconds for jobs to complete
- Logs shutdown status

## 📊 Monitoring with pgAdmin

1. Open http://localhost:5050
2. Login with `admin@admin.com` / `admin`
3. Add server:
   - Name: `Procrastinate`
   - Host: `postgres` (or `localhost` if connecting from host)
   - Port: `5432`
   - Username: `procrastinate`
   - Password: `procrastinate`

### Key Tables to Monitor

- **procrastinate_jobs**: All jobs (queued, running, succeeded, failed)
- **procrastinate_events**: Job execution history
- **chuck_norris_jokes**: Cached API results

### Useful Queries

```sql
-- View all jobs
SELECT id, task_name, status, attempts, scheduled_at 
FROM procrastinate_jobs 
ORDER BY scheduled_at DESC;

-- Count jobs by status
SELECT status, COUNT(*) 
FROM procrastinate_jobs 
GROUP BY status;

-- View failed jobs
SELECT id, task_name, attempts, scheduled_at 
FROM procrastinate_jobs 
WHERE status = 'failed';

-- View cached jokes
SELECT joke_id, category, created_at 
FROM chuck_norris_jokes 
ORDER BY created_at DESC;
```

## 🧪 Testing

### Manual Testing

1. **Test Normal Operation**:
   ```bash
   curl -X POST http://localhost:8000/tasks/fetch-joke
   ```

2. **Test Retry Logic** (simulate API failure):
   - Stop your internet connection
   - Submit a job
   - Observe retries in logs
   - Restore connection
   - Job should eventually succeed

3. **Test Crash Recovery**:
   - Submit several jobs
   - Kill the application (Ctrl+C)
   - Restart the application
   - Stalled jobs should be automatically retried

### Automated Testing

```bash
# Run tests (add pytest later)
pytest tests/
```

## 📁 Project Structure

```
procrastinate-demo/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration management
│   ├── database.py          # Database setup
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── tasks.py             # Procrastinate tasks
│   └── procrastinate_app.py # Procrastinate configuration
├── docker-compose.yml       # Docker services
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables
├── .env.example            # Example environment file
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## 🔍 How It Works

### Task Execution Flow

1. **Job Submission**: Client sends POST request to `/tasks/fetch-joke`
2. **Job Queuing**: FastAPI defers task to Procrastinate queue
3. **Worker Pickup**: Background worker picks up job from queue
4. **Execution**: Task fetches data from Chuck Norris API
5. **Caching**: Result is stored in PostgreSQL with upsert
6. **Retry on Failure**: If task fails, it's automatically retried with exponential backoff
7. **Status Update**: Job status is updated in database

### Periodic Tasks

Two periodic tasks run automatically:

1. **Scheduled Fetch** (every 2 minutes):
   - Automatically fetches a random joke
   - Demonstrates periodic task scheduling

2. **Stalled Job Retry** (every 10 minutes):
   - Detects jobs that were interrupted
   - Automatically retries them
   - Ensures bulletproof task completion

## 🚨 Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker-compose ps

# View PostgreSQL logs
docker-compose logs postgres

# Restart services
docker-compose restart
```

### Worker Not Processing Jobs

```bash
# Check application logs
# Look for "Procrastinate worker started"

# Verify worker is running
ps aux | grep uvicorn

# Check job queue
# Use pgAdmin to query procrastinate_jobs table
```

### Port Already in Use

```bash
# Change port in docker-compose.yml or when starting uvicorn
uvicorn app.main:app --reload --port 8001
```

## 🎓 Learning Resources

- [Procrastinate Documentation](https://procrastinate.readthedocs.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Chuck Norris API](https://api.chucknorris.io/)

## 📝 License

MIT License - feel free to use this for learning or production!

## 🤝 Contributing

Contributions welcome! This is a demo project showcasing best practices.

## 🎉 Next Steps

- Add authentication and authorization
- Implement rate limiting
- Add comprehensive test suite
- Set up CI/CD pipeline
- Add metrics and observability (Prometheus, Grafana)
- Deploy to production (Docker, Kubernetes)
