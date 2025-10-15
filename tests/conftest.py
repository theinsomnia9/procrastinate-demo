"""
Pytest configuration and fixtures for testing.
"""
import pytest
import asyncio
from typing import Generator


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
