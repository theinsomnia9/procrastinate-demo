# Getting Started - Visual Guide

## 🎯 What You're Building

A production-ready task scheduling system that:
- ✅ Fetches Chuck Norris jokes from an API
- ✅ Caches them in PostgreSQL
- ✅ Automatically retries on failure
- ✅ Recovers from crashes
- ✅ Provides a REST API and monitoring UI

## 📋 Prerequisites Checklist

Before starting, ensure you have:

- [ ] Docker installed and running
- [ ] Python 3.11+ installed
- [ ] Terminal/command line access
- [ ] Web browser
- [ ] 5-10 minutes of time

## 🚀 Step-by-Step Setup

### Step 1: Navigate to Project Directory

```bash
cd /home/homie/projects/procrastinate-demo
```

### Step 2: Start Database Services

```bash
# Start PostgreSQL and pgAdmin
docker-compose up -d

# Verify services are running
docker-compose ps
```

**Expected Output:**
```
NAME                      STATUS    PORTS
procrastinate_postgres    Up        0.0.0.0:5432->5432/tcp
procrastinate_pgadmin     Up        0.0.0.0:5050->80/tcp
```

**Wait 10 seconds** for PostgreSQL to initialize.

### Step 3: Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # On Linux/Mac
# OR
venv\Scripts\activate     # On Windows
```

**You should see** `(venv)` in your terminal prompt.

### Step 4: Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Expected:** Installation of ~15 packages (FastAPI, Procrastinate, SQLAlchemy, etc.)

### Step 5: Initialize Database

```bash
python scripts/init_db.py
```

**Expected Output:**
```
Initializing database tables...
✓ Database tables created

Applying Procrastinate schema...
✓ Procrastinate schema applied

✅ Database initialization complete!
```

### Step 6: Start the Application

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Keep this terminal open!** The application is now running.

## 🎉 Verify It's Working

### Test 1: Open the Web UI

Open your browser to: **http://localhost:8000**

You should see a nice landing page with:
- List of available endpoints
- Links to documentation
- Feature list

### Test 2: Submit a Task

Open a **new terminal** and run:

```bash
curl -X POST http://localhost:8000/tasks/fetch-joke \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response:**
```json
{
  "job_id": 1,
  "status": "queued",
  "message": "Job 1 queued successfully. Category: random"
}
```

### Test 3: Check Job Status

```bash
curl http://localhost:8000/jobs/1
```

**Expected Response:**
```json
{
  "job_id": 1,
  "task_name": "app.tasks.fetch_and_cache_joke",
  "status": "succeeded",
  "attempts": 1,
  "scheduled_at": "2024-10-13T18:30:00Z",
  "started_at": "2024-10-13T18:30:01Z",
  "queue_name": "api_calls"
}
```

### Test 4: View Cached Jokes

```bash
curl http://localhost:8000/jokes
```

**Expected Response:**
```json
[
  {
    "id": 1,
    "joke_id": "abc123",
    "category": null,
    "joke_text": "Chuck Norris can divide by zero.",
    "icon_url": "https://...",
    "url": "https://...",
    "created_at": "2024-10-13T18:30:01Z",
    "updated_at": "2024-10-13T18:30:01Z"
  }
]
```

## 🎨 Explore the UI

### 1. Interactive API Documentation

Open: **http://localhost:8000/docs**

Features:
- Try out all endpoints
- See request/response schemas
- Test authentication (if added)

### 2. Database UI (pgAdmin)

Open: **http://localhost:5050**

**Login:**
- Email: `admin@admin.com`
- Password: `admin`

**Add Server:**
1. Click "Add New Server"
2. General tab:
   - Name: `Procrastinate`
3. Connection tab:
   - Host: `postgres` (if in Docker) or `localhost` (if on host)
   - Port: `5432`
   - Username: `procrastinate`
   - Password: `procrastinate`
   - Database: `procrastinate_db`
4. Click "Save"

**Explore Tables:**
- `chuck_norris_jokes` - Your cached data
- `procrastinate_jobs` - Job queue and status
- `procrastinate_events` - Job execution history

## 🧪 Test Advanced Features

### Test Retry Logic

```bash
# Submit multiple tasks
python scripts/test_task.py 10
```

**Watch the logs** in your application terminal to see:
- Tasks being picked up
- API calls being made
- Results being cached

### Test Periodic Tasks

Just wait! The application automatically:
- Fetches a random joke every 2 minutes
- Checks for stalled jobs every 10 minutes

**Check the logs** to see periodic tasks running.

### Test Crash Recovery

1. Submit several tasks:
   ```bash
   python scripts/test_task.py 20
   ```

2. **Immediately** kill the application (Ctrl+C)

3. Check database for incomplete jobs:
   ```sql
   SELECT * FROM procrastinate_jobs WHERE status = 'doing';
   ```

4. Restart the application:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. Wait 10 minutes for the stalled job retry task to run

6. **Verify** all jobs eventually complete

## 📊 Monitor Your System

### View Job Statistics

```bash
curl http://localhost:8000/stats
```

### Check Application Health

```bash
curl http://localhost:8000/health
```

### Query Database Directly

```bash
# Connect to PostgreSQL
docker exec -it procrastinate_postgres psql -U procrastinate -d procrastinate_db

# View all jobs
SELECT id, task_name, status, attempts FROM procrastinate_jobs ORDER BY id DESC LIMIT 10;

# Count by status
SELECT status, COUNT(*) FROM procrastinate_jobs GROUP BY status;

# Exit
\q
```

## 🎓 Understanding the Flow

### When You Submit a Task:

```
1. HTTP Request → FastAPI Endpoint
   POST /tasks/fetch-joke

2. FastAPI → Procrastinate
   defer_async(category=None)

3. Procrastinate → PostgreSQL
   INSERT INTO procrastinate_jobs (...)

4. Response to Client
   {"job_id": 1, "status": "queued"}

5. Background Worker (running in same process)
   - Polls database for jobs
   - Picks up job 1
   - Executes fetch_and_cache_joke()

6. Task Execution
   - Fetch from Chuck Norris API
   - Cache in chuck_norris_jokes table
   - Update job status to "succeeded"

7. You Can Query
   GET /jobs/1 → See status
   GET /jokes → See cached data
```

### When a Task Fails:

```
1. Task Raises Exception
   httpx.TimeoutException

2. Procrastinate Catches It
   - Increment attempts
   - Calculate backoff delay
   - Reschedule job

3. Retry After Delay
   Attempt 1: immediate
   Attempt 2: 2 seconds later
   Attempt 3: 4 seconds later
   Attempt 4: 8 seconds later
   Attempt 5: 16 seconds later

4. Eventually Succeeds or Fails
   - Success: status = "succeeded"
   - Max retries: status = "failed"
```

## 🛠️ Useful Commands

### Application Management

```bash
# Start everything
./start.sh

# Or use Make
make start      # Start Docker services
make install    # Install Python deps
make db-init    # Initialize database
make run        # Run application

# Stop services
docker-compose stop

# View logs
docker-compose logs -f postgres
docker-compose logs -f pgadmin

# Clean up everything
make clean
docker-compose down -v
```

### Development

```bash
# Run standalone worker (separate from API)
python scripts/run_worker.py

# Submit test tasks
python scripts/test_task.py 5

# Check Python version
python --version

# List installed packages
pip list
```

## 🐛 Troubleshooting

### Problem: "Port 5432 already in use"

**Solution:**
```bash
# Stop existing PostgreSQL
sudo systemctl stop postgresql
# OR
docker stop $(docker ps -q --filter "expose=5432")

# Then restart
docker-compose up -d
```

### Problem: "Module not found"

**Solution:**
```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Problem: "Database connection failed"

**Solution:**
```bash
# Check if PostgreSQL is running
docker-compose ps

# Check logs
docker-compose logs postgres

# Restart
docker-compose restart postgres

# Wait 10 seconds and try again
```

### Problem: "Worker not processing jobs"

**Solution:**
```bash
# Check application logs
# Look for "Procrastinate worker started"

# Verify in database
docker exec -it procrastinate_postgres psql -U procrastinate -d procrastinate_db
SELECT * FROM procrastinate_jobs WHERE status = 'todo';
\q

# Restart application
# Ctrl+C and run uvicorn again
```

## 📚 Next Steps

Now that you have it running:

1. **Read the Documentation**
   - `README.md` - Complete guide
   - `ARCHITECTURE.md` - How it works
   - `DEVELOPMENT.md` - Extend and customize

2. **Experiment**
   - Add new tasks
   - Try different APIs
   - Modify retry strategies
   - Add new endpoints

3. **Deploy**
   - Containerize with Docker
   - Deploy to cloud
   - Set up monitoring
   - Add authentication

## 🎉 Congratulations!

You now have a bulletproof task scheduling system running! 

**What you've learned:**
- ✅ Async Python with FastAPI
- ✅ Task queues with Procrastinate
- ✅ PostgreSQL with SQLAlchemy
- ✅ Docker Compose
- ✅ Retry strategies
- ✅ Error handling
- ✅ API design

**Keep exploring and building amazing things!** 🚀
