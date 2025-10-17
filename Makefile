.PHONY: help install install-test start stop restart logs db-init worker test-tasks clean test test-unit test-integration test-stress test-stress-quick test-all coverage

help:
	@echo "Available commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make install           - Install Python dependencies"
	@echo "  make install-test      - Install test dependencies"
	@echo "  make start             - Start Docker services (PostgreSQL, pgAdmin)"
	@echo "  make stop              - Stop Docker services"
	@echo "  make restart           - Restart Docker services"
	@echo ""
	@echo "Running:"
	@echo "  make run               - Run FastAPI application with worker"
	@echo "  make worker            - Run standalone worker"
	@echo "  make logs              - View Docker logs"
	@echo "  make db-init           - Initialize database and Procrastinate schema"
	@echo ""
	@echo "Tracing:"
	@echo "  make tracing-start     - Start services with Jaeger for tracing"
	@echo "  make tracing-demo      - Run OpenTelemetry tracing demo"
	@echo "  make tracing-simple    - Run simple tracing example"
	@echo "  make jaeger-ui         - Open Jaeger UI in browser"
	@echo ""
	@echo "Testing:"
	@echo "  make test              - Run all unit and integration tests"
	@echo "  make test-unit         - Run unit tests only"
	@echo "  make test-integration  - Run integration tests only"
	@echo "  make test-stress       - Run exponential backoff stress tests"
	@echo "  make test-stress-quick - Run quick system stress tests"
	@echo "  make test-all          - Run all tests including stress tests"
	@echo "  make coverage          - Run tests with coverage report"
	@echo "  make test-tasks        - Submit test tasks manually"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean             - Clean up containers and volumes"

install:
	pip install -r requirements.txt

install-test:
	pip install -r requirements-test.txt

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

# Testing commands
test:
	@echo "Running unit and integration tests..."
	pytest tests/ -v

test-unit:
	@echo "Running unit tests..."
	pytest tests/test_exponential_backoff.py -v

test-integration:
	@echo "Running integration tests..."
	pytest tests/test_integration.py -v

test-stress:
	@echo "Running exponential backoff stress tests..."
	python scripts/stress_test_exponential_backoff.py

test-stress-quick:
	@echo "Running quick system stress tests..."
	python scripts/stress_test_system.py --quick

test-stress-full:
	@echo "Running full system stress tests..."
	python scripts/stress_test_system.py --tasks 100

test-all: test test-stress test-stress-quick
	@echo ""
	@echo "✅ All tests completed!"

coverage:
	@echo "Running tests with coverage..."
	pytest tests/ --cov=app --cov-report=html --cov-report=term
	@echo ""
	@echo "Coverage report generated in htmlcov/index.html"

# Tracing commands
tracing-start:
	docker-compose up -d postgres jaeger
	@echo "Waiting for services to be ready..."
	@sleep 10
	@echo "✓ Tracing services started"
	@echo "  PostgreSQL: localhost:5432"
	@echo "  Jaeger UI: http://localhost:16686"

tracing-demo:
	python tracing_demo.py

tracing-simple:
	python simple_tracing_example.py

jaeger-ui:
	@echo "Opening Jaeger UI..."
	@python -c "import webbrowser; webbrowser.open('http://localhost:16686')"

clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov/ .coverage .pytest_cache/ 2>/dev/null || true
