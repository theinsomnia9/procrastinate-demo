"""
Unit tests for ExponentialBackoffStrategy.

Tests verify:
- Correct exponential delay calculation
- Max attempts enforcement
- Max delay cap
- Exception-specific retry logic
"""
import pytest
from app.procrastinate_app import ExponentialBackoffStrategy


class TestExponentialBackoffStrategy:
    """Test suite for ExponentialBackoffStrategy class."""
    
    def test_exponential_delay_calculation(self):
        """Test that delays follow exponential pattern (2^n)."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
            max_delay=300.0,
        )
        
        # Test delay progression
        expected_delays = [
            (0, 2),    # 2 * 2^0 = 2
            (1, 4),    # 2 * 2^1 = 4
            (2, 8),    # 2 * 2^2 = 8
            (3, 16),   # 2 * 2^3 = 16
            (4, 32),   # 2 * 2^4 = 32
        ]
        
        for attempts, expected_delay in expected_delays:
            result = strategy.get_schedule_in(attempts=attempts)
            assert result is not None
            assert result["seconds"] == expected_delay
    
    def test_max_attempts_enforcement(self):
        """Test that retries stop after max_attempts."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=3,
            base_delay=2.0,
        )
        
        # Attempts 0, 1, 2 should return delays
        assert strategy.get_schedule_in(attempts=0) is not None
        assert strategy.get_schedule_in(attempts=1) is not None
        assert strategy.get_schedule_in(attempts=2) is not None
        
        # Attempt 3 should return None (stop retrying)
        assert strategy.get_schedule_in(attempts=3) is None
        assert strategy.get_schedule_in(attempts=4) is None
    
    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=10,
            base_delay=2.0,
            max_delay=60.0,  # Cap at 60 seconds
        )
        
        # Early attempts should be under cap
        result = strategy.get_schedule_in(attempts=0)
        assert result["seconds"] == 2  # 2 * 2^0 = 2
        
        result = strategy.get_schedule_in(attempts=3)
        assert result["seconds"] == 16  # 2 * 2^3 = 16
        
        # Later attempts should hit the cap
        result = strategy.get_schedule_in(attempts=6)
        # 2 * 2^6 = 128, but capped at 60
        assert result["seconds"] == 60
        
        result = strategy.get_schedule_in(attempts=8)
        # 2 * 2^8 = 512, but capped at 60
        assert result["seconds"] == 60
    
    def test_exception_filtering_with_allowed_exception(self):
        """Test that allowed exceptions trigger retry."""
        class AllowedException(Exception):
            pass
        
        class OtherException(Exception):
            pass
        
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
            retry_exceptions=[AllowedException],
        )
        
        # Allowed exception should trigger retry
        result = strategy.get_schedule_in(
            attempts=0,
            exception=AllowedException("test")
        )
        assert result is not None
        assert result["seconds"] == 2
    
    def test_exception_filtering_with_disallowed_exception(self):
        """Test that disallowed exceptions do not trigger retry."""
        class AllowedException(Exception):
            pass
        
        class DisallowedException(Exception):
            pass
        
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
            retry_exceptions=[AllowedException],
        )
        
        # Disallowed exception should not trigger retry
        result = strategy.get_schedule_in(
            attempts=0,
            exception=DisallowedException("test")
        )
        assert result is None
    
    def test_no_exception_filter_retries_all(self):
        """Test that None retry_exceptions retries all exceptions."""
        class AnyException(Exception):
            pass
        
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
            retry_exceptions=None,  # Retry all exceptions
        )
        
        # Any exception should trigger retry
        result = strategy.get_schedule_in(
            attempts=0,
            exception=AnyException("test")
        )
        assert result is not None
        assert result["seconds"] == 2
    
    def test_different_base_delays(self):
        """Test strategy with different base delays."""
        # Fast retry (1 second base)
        fast_strategy = ExponentialBackoffStrategy(
            max_attempts=3,
            base_delay=1.0,
        )
        assert fast_strategy.get_schedule_in(attempts=0)["seconds"] == 1
        assert fast_strategy.get_schedule_in(attempts=1)["seconds"] == 2
        assert fast_strategy.get_schedule_in(attempts=2)["seconds"] == 4
        
        # Slow retry (5 second base)
        slow_strategy = ExponentialBackoffStrategy(
            max_attempts=3,
            base_delay=5.0,
        )
        assert slow_strategy.get_schedule_in(attempts=0)["seconds"] == 5
        assert slow_strategy.get_schedule_in(attempts=1)["seconds"] == 10
        assert slow_strategy.get_schedule_in(attempts=2)["seconds"] == 20
    
    def test_zero_attempts(self):
        """Test behavior with zero attempts (first try)."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
        )
        
        result = strategy.get_schedule_in(attempts=0)
        assert result is not None
        assert result["seconds"] == 2  # 2 * 2^0 = 2
    
    def test_large_attempt_numbers(self):
        """Test behavior with large attempt numbers."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=20,
            base_delay=1.0,
            max_delay=3600.0,  # 1 hour cap
        )
        
        # Attempt 10: 1 * 2^10 = 1024 seconds
        result = strategy.get_schedule_in(attempts=10)
        assert result["seconds"] == 1024
        
        # Attempt 15: 1 * 2^15 = 32768, but capped at 3600
        result = strategy.get_schedule_in(attempts=15)
        assert result["seconds"] == 3600
    
    def test_multiple_exception_types(self):
        """Test retry logic with multiple exception types."""
        class ExceptionA(Exception):
            pass
        
        class ExceptionB(Exception):
            pass
        
        class ExceptionC(Exception):
            pass
        
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
            retry_exceptions=[ExceptionA, ExceptionB],
        )
        
        # ExceptionA should retry
        result = strategy.get_schedule_in(attempts=0, exception=ExceptionA("test"))
        assert result is not None
        
        # ExceptionB should retry
        result = strategy.get_schedule_in(attempts=0, exception=ExceptionB("test"))
        assert result is not None
        
        # ExceptionC should not retry
        result = strategy.get_schedule_in(attempts=0, exception=ExceptionC("test"))
        assert result is None
    
    def test_cumulative_delay_time(self):
        """Test total time spent in retries."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
            max_delay=300.0,
        )
        
        total_delay = 0
        for attempt in range(5):
            result = strategy.get_schedule_in(attempts=attempt)
            if result:
                total_delay += result["seconds"]
        
        # Total: 2 + 4 + 8 + 16 + 32 = 62 seconds
        assert total_delay == 62
    
    def test_strategy_immutability(self):
        """Test that strategy parameters don't change between calls."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
            max_delay=300.0,
        )
        
        # Multiple calls should return same results
        result1 = strategy.get_schedule_in(attempts=2)
        result2 = strategy.get_schedule_in(attempts=2)
        
        assert result1 == result2
        assert result1["seconds"] == 8


class TestExponentialBackoffEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_max_attempts_one(self):
        """Test with max_attempts=1 (no retries)."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=1,
            base_delay=2.0,
        )
        
        # First attempt (0) should work
        result = strategy.get_schedule_in(attempts=0)
        assert result is not None
        
        # Second attempt (1) should return None
        result = strategy.get_schedule_in(attempts=1)
        assert result is None
    
    def test_very_small_base_delay(self):
        """Test with very small base delay."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=0.1,
        )
        
        result = strategy.get_schedule_in(attempts=0)
        assert result["seconds"] == 0  # int(0.1) = 0
        
        result = strategy.get_schedule_in(attempts=1)
        assert result["seconds"] == 0  # int(0.2) = 0
        
        result = strategy.get_schedule_in(attempts=3)
        assert result["seconds"] == 0  # int(0.8) = 0
        
        result = strategy.get_schedule_in(attempts=4)
        assert result["seconds"] == 1  # int(1.6) = 1
    
    def test_max_delay_smaller_than_base(self):
        """Test when max_delay is smaller than base_delay."""
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=10.0,
            max_delay=5.0,  # Smaller than base
        )
        
        # All delays should be capped at max_delay
        for attempt in range(5):
            result = strategy.get_schedule_in(attempts=attempt)
            assert result is not None
            assert result["seconds"] == 5
    
    def test_exception_inheritance(self):
        """Test that exception inheritance is handled correctly."""
        class BaseException_(Exception):
            pass
        
        class DerivedException(BaseException_):
            pass
        
        strategy = ExponentialBackoffStrategy(
            max_attempts=5,
            base_delay=2.0,
            retry_exceptions=[BaseException_],
        )
        
        # Derived exception should trigger retry (isinstance check)
        result = strategy.get_schedule_in(
            attempts=0,
            exception=DerivedException("test")
        )
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
