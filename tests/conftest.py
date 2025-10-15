"""
Pytest configuration and fixtures for testing.
"""
import pytest
import asyncio
from typing import Generator
from procrastinate import testing


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    from unittest.mock import MagicMock
    settings = MagicMock()
    settings.max_retries = 5
    settings.retry_base_delay = 2.0
    settings.retry_max_delay = 300.0
    settings.job_timeout = 300
    settings.worker_concurrency = 10
    settings.worker_timeout = 30
    settings.api_base_url = "https://api.chucknorris.io"
    return settings


@pytest.fixture
def in_memory_connector():
    """
    Create an in-memory connector for isolated testing.
    
    This fixture provides a fresh InMemoryConnector that simulates
    a database without requiring actual database connections.
    Ideal for fast, isolated unit tests.
    """
    connector = testing.InMemoryConnector()
    yield connector
    # Cleanup after test
    connector.reset()


@pytest.fixture
async def in_memory_app(in_memory_connector):
    """
    Create a test app instance with in-memory connector.
    
    This fixture provides a complete Procrastinate app configured
    with an in-memory connector for testing without a real database.
    """
    from app.procrastinate_app import app
    
    async with app.replace_connector(in_memory_connector) as test_app:
        yield test_app


@pytest.fixture
def performance_threshold():
    """
    Performance thresholds for throughput tests.
    
    Returns a dict of minimum acceptable performance metrics.
    Adjust these values based on your performance requirements.
    """
    return {
        'min_deferral_rate': 50,  # tasks per second
        'min_processing_rate': 10,  # tasks per second
        'max_latency_ms': 1000,  # milliseconds
        'max_queue_wait_ms': 5000,  # milliseconds
    }
