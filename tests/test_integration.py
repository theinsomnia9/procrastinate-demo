"""
Integration tests for task execution with exponential backoff.

Tests verify:
- Tasks retry with exponential delays
- Stalled job recovery works
- Job timeout protection works
- Idempotent operations
"""
import pytest
import asyncio
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.procrastinate_app import app, ExponentialBackoffStrategy
from app.tasks import fetch_and_cache_joke, TaskError
from app.config import get_settings

settings = get_settings()


@pytest.mark.asyncio
class TestTaskRetryBehavior:
    """Test task retry behavior with exponential backoff."""
    
    async def test_task_succeeds_on_first_attempt(self):
        """Test that successful tasks don't retry."""
        mock_context = MagicMock()
        mock_context.job.attempts = 1
        mock_context.job.id = 1
        
        with patch('app.tasks._fetch_joke_from_api') as mock_fetch, \
             patch('app.tasks._cache_joke_in_db') as mock_cache:
            
            mock_fetch.return_value = {
                'id': 'test-joke-1',
                'value': 'Test joke',
                'categories': ['dev'],
                'icon_url': 'http://example.com/icon.png',
                'url': 'http://example.com/joke'
            }
            mock_cache.return_value = None
            
            result = await fetch_and_cache_joke(mock_context, category='dev')
            
            assert result['status'] == 'success'
            assert result['joke_id'] == 'test-joke-1'
            assert result['attempt'] == 1
            
            # Should be called exactly once
            mock_fetch.assert_called_once()
            mock_cache.assert_called_once()
    
    async def test_task_retries_on_http_error(self):
        """Test that HTTP errors trigger retry."""
        mock_context = MagicMock()
        mock_context.job.attempts = 1
        mock_context.job.id = 1
        
        with patch('app.tasks._fetch_joke_from_api') as mock_fetch:
            mock_fetch.side_effect = httpx.HTTPError("API error")
            
            with pytest.raises(TaskError) as exc_info:
                await fetch_and_cache_joke(mock_context, category='dev')
            
            assert "HTTP error" in str(exc_info.value)
    
    async def test_task_retries_on_timeout(self):
        """Test that timeouts trigger retry."""
        mock_context = MagicMock()
        mock_context.job.attempts = 1
        mock_context.job.id = 1
        
        with patch('app.tasks._fetch_joke_from_api') as mock_fetch:
            mock_fetch.side_effect = httpx.TimeoutException("Timeout")
            
            with pytest.raises(TaskError) as exc_info:
                await fetch_and_cache_joke(mock_context, category='dev')
            
            assert "API timeout" in str(exc_info.value)
    
    async def test_task_timeout_protection(self):
        """Test that job timeout prevents hanging tasks."""
        mock_context = MagicMock()
        mock_context.job.attempts = 1
        mock_context.job.id = 1
        
        async def slow_fetch(*args, **kwargs):
            # Simulate a task that takes longer than timeout
            await asyncio.sleep(settings.job_timeout + 1)
            return {'id': 'test', 'value': 'joke', 'categories': []}
        
        with patch('app.tasks._fetch_joke_from_api', side_effect=slow_fetch):
            with pytest.raises(TaskError) as exc_info:
                await fetch_and_cache_joke(mock_context, category='dev')
            
            assert "timeout" in str(exc_info.value).lower()


@pytest.mark.asyncio
class TestExponentialBackoffIntegration:
    """Test exponential backoff integration with tasks."""
    
    async def test_retry_strategy_configuration(self):
        """Test that tasks are configured with correct retry strategy."""
        # Check main task configuration
        task = fetch_and_cache_joke
        assert hasattr(task, 'retry')
        assert isinstance(task.retry, ExponentialBackoffStrategy)
        assert task.retry.max_attempts == settings.max_retries
        assert task.retry.base_delay == settings.retry_base_delay
        assert task.retry.max_delay == settings.retry_max_delay
    
    async def test_exponential_delay_progression(self):
        """Test that retry delays follow exponential pattern."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
            max_delay=300.0,
        )
        
        delays = []
        for attempt in range(5):
            result = strategy.get_schedule_in(attempts=attempt)
            if result:
                delays.append(result['seconds'])
        
        # Verify exponential progression: 2, 4, 8, 16, 32
        assert delays == [2, 4, 8, 16, 32]
        
        # Verify it's exponential (each delay is 2x previous)
        for i in range(1, len(delays)):
            assert delays[i] == delays[i-1] * 2


@pytest.mark.asyncio
class TestIdempotency:
    """Test idempotent operations for safe retries."""
    
    async def test_duplicate_joke_upsert(self):
        """Test that duplicate jokes are handled via upsert."""
        # This test would require database setup
        # Placeholder for integration test
        pass
    
    async def test_retry_does_not_duplicate_data(self):
        """Test that retrying a task doesn't create duplicate records."""
        # This test would require database setup
        # Placeholder for integration test
        pass


@pytest.mark.asyncio
class TestStalledJobRecovery:
    """Test stalled job detection and recovery."""
    
    async def test_stalled_jobs_are_detected(self):
        """Test that stalled jobs are properly detected."""
        # This test would require worker simulation
        # Placeholder for integration test
        pass
    
    async def test_stalled_jobs_are_retried(self):
        """Test that detected stalled jobs are retried."""
        # This test would require worker simulation
        # Placeholder for integration test
        pass


class TestRetryExceptionFiltering:
    """Test that only specified exceptions trigger retries."""
    
    def test_task_error_triggers_retry(self):
        """Test that TaskError is in retry_exceptions."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
            retry_exceptions=[TaskError, httpx.HTTPError, httpx.TimeoutException],
        )
        
        result = strategy.get_schedule_in(
            attempts=0,
            exception=TaskError("test")
        )
        assert result is not None
    
    def test_http_error_triggers_retry(self):
        """Test that HTTPError is in retry_exceptions."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
            retry_exceptions=[TaskError, httpx.HTTPError, httpx.TimeoutException],
        )
        
        result = strategy.get_schedule_in(
            attempts=0,
            exception=httpx.HTTPError("test")
        )
        assert result is not None
    
    def test_timeout_exception_triggers_retry(self):
        """Test that TimeoutException is in retry_exceptions."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
            retry_exceptions=[TaskError, httpx.HTTPError, httpx.TimeoutException],
        )
        
        result = strategy.get_schedule_in(
            attempts=0,
            exception=httpx.TimeoutException("test")
        )
        assert result is not None
    
    def test_value_error_does_not_trigger_retry(self):
        """Test that ValueError does not trigger retry."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
            retry_exceptions=[TaskError, httpx.HTTPError, httpx.TimeoutException],
        )
        
        result = strategy.get_schedule_in(
            attempts=0,
            exception=ValueError("test")
        )
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
