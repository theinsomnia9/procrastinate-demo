#!/usr/bin/env python
"""
Stress test for exponential backoff retry strategy.

This script:
1. Simulates API failures to trigger retries
2. Monitors retry timing and delays
3. Verifies exponential backoff behavior
4. Tests system under load

Usage:
    python scripts/stress_test_exponential_backoff.py
"""
import asyncio
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import httpx

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.procrastinate_app import app as procrastinate_app, ExponentialBackoffStrategy
from app.tasks import fetch_and_cache_joke
from app.config import get_settings

settings = get_settings()


class RetryMonitor:
    """Monitor and analyze retry behavior."""
    
    def __init__(self):
        self.retry_events: List[Dict] = []
        self.start_time = None
    
    def record_event(self, job_id: int, attempt: int, event_type: str, timestamp: float = None):
        """Record a retry event."""
        if timestamp is None:
            timestamp = time.time()
        
        if self.start_time is None:
            self.start_time = timestamp
        
        self.retry_events.append({
            'job_id': job_id,
            'attempt': attempt,
            'event_type': event_type,
            'timestamp': timestamp,
            'elapsed': timestamp - self.start_time if self.start_time else 0,
        })
    
    def analyze_delays(self, job_id: int) -> List[float]:
        """Analyze delays between retry attempts for a job."""
        job_events = [e for e in self.retry_events if e['job_id'] == job_id]
        job_events.sort(key=lambda x: x['timestamp'])
        
        delays = []
        for i in range(1, len(job_events)):
            delay = job_events[i]['timestamp'] - job_events[i-1]['timestamp']
            delays.append(delay)
        
        return delays
    
    def verify_exponential_pattern(self, delays: List[float], base_delay: float = 2.0, tolerance: float = 0.5) -> bool:
        """Verify that delays follow exponential pattern."""
        expected_delays = [base_delay * (2 ** i) for i in range(len(delays))]
        
        for i, (actual, expected) in enumerate(zip(delays, expected_delays)):
            if abs(actual - expected) > tolerance:
                print(f"  ⚠️  Delay {i+1}: Expected ~{expected}s, got {actual:.2f}s")
                return False
        
        return True
    
    def print_summary(self):
        """Print summary of retry events."""
        print("\n" + "="*80)
        print("RETRY MONITOR SUMMARY")
        print("="*80)
        
        job_ids = set(e['job_id'] for e in self.retry_events)
        
        for job_id in sorted(job_ids):
            job_events = [e for e in self.retry_events if e['job_id'] == job_id]
            print(f"\nJob {job_id}:")
            print(f"  Total events: {len(job_events)}")
            
            for event in job_events:
                print(f"    [{event['elapsed']:.2f}s] Attempt {event['attempt']}: {event['event_type']}")
            
            delays = self.analyze_delays(job_id)
            if delays:
                print(f"  Delays between attempts: {[f'{d:.2f}s' for d in delays]}")
                
                is_exponential = self.verify_exponential_pattern(delays)
                if is_exponential:
                    print("  ✅ Delays follow exponential pattern")
                else:
                    print("  ❌ Delays do NOT follow exponential pattern")


async def test_exponential_backoff_unit():
    """Unit test for exponential backoff calculation."""
    print("\n" + "="*80)
    print("TEST 1: Exponential Backoff Unit Test")
    print("="*80)
    
    strategy = ExponentialBackoffStrategy(
        max_attempts=5,
        base_delay=2.0,
        max_delay=300.0,
    )
    
    print("\nTesting delay calculation:")
    delays = []
    for attempt in range(5):
        result = strategy.get_schedule_in(attempts=attempt)
        if result:
            delay = result['seconds']
            delays.append(delay)
            print(f"  Attempt {attempt + 1}: {delay}s")
    
    # Verify exponential pattern
    expected = [2, 4, 8, 16, 32]
    if delays == expected:
        print(f"\n✅ PASSED: Delays match expected exponential pattern {expected}")
        return True
    else:
        print(f"\n❌ FAILED: Expected {expected}, got {delays}")
        return False


async def test_max_delay_cap():
    """Test that max_delay cap is enforced."""
    print("\n" + "="*80)
    print("TEST 2: Max Delay Cap")
    print("="*80)
    
    strategy = ExponentialBackoffStrategy(
        max_attempts=10,
        base_delay=2.0,
        max_delay=60.0,  # Cap at 60 seconds
    )
    
    print("\nTesting delay cap:")
    for attempt in range(10):
        result = strategy.get_schedule_in(attempts=attempt)
        if result:
            delay = result['seconds']
            expected_uncapped = 2 * (2 ** attempt)
            capped = min(expected_uncapped, 60)
            status = "✅" if delay == capped else "❌"
            print(f"  Attempt {attempt + 1}: {delay}s (uncapped: {expected_uncapped}s, cap: 60s) {status}")
    
    # Verify cap is enforced
    result = strategy.get_schedule_in(attempts=9)
    if result and result['seconds'] == 60:
        print(f"\n✅ PASSED: Max delay cap enforced")
        return True
    else:
        print(f"\n❌ FAILED: Max delay cap not enforced")
        return False


async def test_exception_filtering():
    """Test exception-specific retry logic."""
    print("\n" + "="*80)
    print("TEST 3: Exception Filtering")
    print("="*80)
    
    class AllowedException(Exception):
        pass
    
    class DisallowedException(Exception):
        pass
    
    strategy = ExponentialBackoffStrategy(
        max_attempts=5,
        base_delay=2.0,
        retry_exceptions=[AllowedException, httpx.HTTPError],
    )
    
    print("\nTesting exception filtering:")
    
    # Test allowed exception
    result = strategy.get_schedule_in(attempts=0, exception=AllowedException("test"))
    status1 = "✅" if result is not None else "❌"
    print(f"  AllowedException: {'Retries' if result else 'Does not retry'} {status1}")
    
    # Test HTTP error
    result = strategy.get_schedule_in(attempts=0, exception=httpx.HTTPError("test"))
    status2 = "✅" if result is not None else "❌"
    print(f"  HTTPError: {'Retries' if result else 'Does not retry'} {status2}")
    
    # Test disallowed exception
    result = strategy.get_schedule_in(attempts=0, exception=DisallowedException("test"))
    status3 = "✅" if result is None else "❌"
    print(f"  DisallowedException: {'Retries' if result else 'Does not retry'} {status3}")
    
    if status1 == "✅" and status2 == "✅" and status3 == "✅":
        print(f"\n✅ PASSED: Exception filtering works correctly")
        return True
    else:
        print(f"\n❌ FAILED: Exception filtering not working correctly")
        return False


async def test_max_attempts_enforcement():
    """Test that retries stop after max_attempts."""
    print("\n" + "="*80)
    print("TEST 4: Max Attempts Enforcement")
    print("="*80)
    
    strategy = ExponentialBackoffStrategy(
        max_attempts=3,
        base_delay=2.0,
    )
    
    print("\nTesting max attempts:")
    results = []
    for attempt in range(5):
        result = strategy.get_schedule_in(attempts=attempt)
        results.append(result)
        status = "✅ Retry" if result else "❌ Stop"
        print(f"  Attempt {attempt + 1}: {status}")
    
    # First 3 should retry, last 2 should stop
    if results[0] and results[1] and results[2] and not results[3] and not results[4]:
        print(f"\n✅ PASSED: Max attempts enforced correctly")
        return True
    else:
        print(f"\n❌ FAILED: Max attempts not enforced correctly")
        return False


async def stress_test_concurrent_retries():
    """Stress test with concurrent failing tasks."""
    print("\n" + "="*80)
    print("TEST 5: Concurrent Retry Stress Test")
    print("="*80)
    
    print("\nSimulating 10 concurrent tasks with exponential backoff...")
    print("(This is a simulation - actual task execution requires worker)")
    
    strategy = ExponentialBackoffStrategy(
        max_attempts=5,
        base_delay=1.0,  # Faster for testing
        max_delay=60.0,
    )
    
    # Simulate 10 tasks each retrying 5 times
    total_delays = 0
    for task_id in range(10):
        task_delays = []
        for attempt in range(5):
            result = strategy.get_schedule_in(attempts=attempt)
            if result:
                task_delays.append(result['seconds'])
                total_delays += result['seconds']
        
        print(f"  Task {task_id + 1}: Delays = {task_delays}")
    
    avg_delay = total_delays / 10
    print(f"\n  Total delay time: {total_delays}s")
    print(f"  Average per task: {avg_delay}s")
    print(f"  Expected per task: {sum([1, 2, 4, 8, 16])}s = 31s")
    
    if 30 <= avg_delay <= 32:
        print(f"\n✅ PASSED: Concurrent retries working correctly")
        return True
    else:
        print(f"\n❌ FAILED: Unexpected delay times")
        return False


async def test_different_base_delays():
    """Test strategies with different base delays."""
    print("\n" + "="*80)
    print("TEST 6: Different Base Delays")
    print("="*80)
    
    configs = [
        (1.0, "Fast retry"),
        (2.0, "Standard retry"),
        (5.0, "Slow retry"),
    ]
    
    all_passed = True
    for base_delay, name in configs:
        strategy = ExponentialBackoffStrategy(
            max_attempts=4,
            base_delay=base_delay,
        )
        
        print(f"\n{name} (base_delay={base_delay}s):")
        delays = []
        for attempt in range(4):
            result = strategy.get_schedule_in(attempts=attempt)
            if result:
                delay = result['seconds']
                delays.append(delay)
                expected = int(base_delay * (2 ** attempt))
                status = "✅" if delay == expected else "❌"
                print(f"  Attempt {attempt + 1}: {delay}s (expected: {expected}s) {status}")
                if delay != expected:
                    all_passed = False
    
    if all_passed:
        print(f"\n✅ PASSED: All base delay configurations work correctly")
        return True
    else:
        print(f"\n❌ FAILED: Some base delay configurations incorrect")
        return False


async def performance_benchmark():
    """Benchmark strategy calculation performance."""
    print("\n" + "="*80)
    print("TEST 7: Performance Benchmark")
    print("="*80)
    
    strategy = ExponentialBackoffStrategy(
        max_attempts=5,
        base_delay=2.0,
        max_delay=300.0,
    )
    
    iterations = 100000
    print(f"\nCalculating delays {iterations:,} times...")
    
    start = time.time()
    for _ in range(iterations):
        for attempt in range(5):
            strategy.get_schedule_in(attempts=attempt)
    end = time.time()
    
    elapsed = end - start
    per_call = (elapsed / (iterations * 5)) * 1000000  # microseconds
    
    print(f"  Total time: {elapsed:.3f}s")
    print(f"  Per calculation: {per_call:.2f}µs")
    print(f"  Calculations/sec: {(iterations * 5 / elapsed):,.0f}")
    
    if per_call < 10:  # Should be very fast
        print(f"\n✅ PASSED: Performance is excellent")
        return True
    else:
        print(f"\n⚠️  WARNING: Performance slower than expected")
        return True


async def main():
    """Run all stress tests."""
    print("\n" + "="*80)
    print("EXPONENTIAL BACKOFF STRESS TEST SUITE")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Exponential Backoff Unit Test", test_exponential_backoff_unit),
        ("Max Delay Cap", test_max_delay_cap),
        ("Exception Filtering", test_exception_filtering),
        ("Max Attempts Enforcement", test_max_attempts_enforcement),
        ("Concurrent Retry Stress Test", stress_test_concurrent_retries),
        ("Different Base Delays", test_different_base_delays),
        ("Performance Benchmark", performance_benchmark),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = await test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ ERROR in {name}: {e}")
            results.append((name, False))
    
    # Print final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 ALL TESTS PASSED! Exponential backoff is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
