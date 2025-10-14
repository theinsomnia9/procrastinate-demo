# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Step 1: Start the Database (30 seconds)

```bash
cd /home/homie/projects/procrastinate-demo
docker-compose up -d
```

Wait for PostgreSQL to be ready (~10 seconds).

### Step 2: Set Up Python Environment (2 minutes)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Initialize Database (30 seconds)

```bash
python scripts/init_db.py
```

### Step 4: Run the Application (10 seconds)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 5: Test It! (1 minute)

Open your browser to http://localhost:8000 or try:

```bash
# Submit a task
curl -X POST http://localhost:8000/tasks/fetch-joke \
  -H "Content-Type: application/json" \
  -d '{}'

# Check the result
curl http://localhost:8000/jokes
```

## 🎯 What You Get

✅ **FastAPI server** running on http://localhost:8000  
✅ **Background worker** processing tasks automatically  
✅ **PostgreSQL database** with job queue and cache  
✅ **pgAdmin UI** at http://localhost:5050 (admin@admin.com / admin)  
✅ **Automatic retries** with exponential backoff  
✅ **Crash recovery** for interrupted jobs  

## 📚 Next Steps

1. **Explore the API**: http://localhost:8000/docs
2. **View the database**: http://localhost:5050
3. **Read the docs**: See README.md for detailed information
4. **Test tasks**: `python scripts/test_task.py 10`

## 🛠️ Common Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose stop

# View logs
docker-compose logs -f

# Run application
uvicorn app.main:app --reload

# Submit test tasks
python scripts/test_task.py 10

# Run standalone worker
python scripts/run_worker.py
```

## 🆘 Troubleshooting

**Database won't start?**
```bash
docker-compose down -v
docker-compose up -d
```

**Port 8000 in use?**
```bash
uvicorn app.main:app --reload --port 8001
```

**Dependencies won't install?**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 📖 Documentation

- **README.md** - Complete documentation
- **ARCHITECTURE.md** - System design and architecture
- **DEVELOPMENT.md** - Development guide and best practices

## 🎉 You're Ready!

Your bulletproof task scheduling system is now running. Start building amazing things!
