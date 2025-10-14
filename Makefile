.PHONY: help install start stop restart logs db-init worker test-tasks clean

help:
	@echo "Available commands:"
	@echo "  make install      - Install Python dependencies"
	@echo "  make start        - Start Docker services (PostgreSQL, pgAdmin)"
	@echo "  make stop         - Stop Docker services"
	@echo "  make restart      - Restart Docker services"
	@echo "  make logs         - View Docker logs"
	@echo "  make db-init      - Initialize database and Procrastinate schema"
	@echo "  make run          - Run FastAPI application with worker"
	@echo "  make worker       - Run standalone worker"
	@echo "  make test-tasks   - Submit test tasks"
	@echo "  make clean        - Clean up containers and volumes"

install:
	pip install -r requirements.txt

start:
	docker-compose up -d
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 10
	@echo "✓ Services started"
	@echo "  PostgreSQL: localhost:5432"
	@echo "  pgAdmin: http://localhost:5050"

stop:
	docker-compose stop

restart:
	docker-compose restart

logs:
	docker-compose logs -f

db-init:
	python scripts/init_db.py

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	python scripts/run_worker.py

test-tasks:
	python scripts/test_task.py 10

clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
