# 🧪 Testing Guide - Exponential Backoff & System Reliability

## Overview

This document describes the comprehensive test suite for verifying exponential backoff retry strategy and overall system reliability.

## 📁 Test Structure

```
tests/
├── __init__.py
├── conftest.py                      # Pytest configuration and fixtures
├── test_exponential_backoff.py      # Unit tests for retry strategy
└── test_integration.py              # Integration tests for tasks

scripts/
├── stress_test_exponential_backoff.py  # Stress tests for retry logic
├── stress_test_system.py               # System-wide stress tests
└── test_task.py                        # Manual task submission
```

## 🚀 Quick Start

### Install Test Dependencies

```bash
pip install -r requirements-test.txt
```

### Run All Tests

```bash
# Run unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test file
pytest tests/test_exponential_backoff.py -v

# Run stress tests
python scripts/stress_test_exponential_backoff.py
python scripts/stress_test_system.py --quick
```

## 📊 Test Categories

### 1. Unit Tests - Exponential Backoff Strategy

**File**: `tests/test_exponential_backoff.py`

**Tests**:
- ✅ Exponential delay calculation (2^n pattern)
- ✅ Max attempts enforcement
- ✅ Max delay cap
- ✅ Exception-specific retry logic
- ✅ Different base delays
- ✅ Edge cases and boundary conditions

**Run**:
```bash
pytest tests/test_exponential_backoff.py -v
```

**Example Output**:
```
test_exponential_backoff.py::TestExponentialBackoffStrategy::test_exponential_delay_calculation PASSED
test_exponential_backoff.py::TestExponentialBackoffStrategy::test_max_attempts_enforcement PASSED
test_exponential_backoff.py::TestExponentialBackoffStrategy::test_max_delay_cap PASSED
test_exponential_backoff.py::TestExponentialBackoffStrategy::test_exception_filtering_with_allowed_exception PASSED
...
```

### 2. Integration Tests - Task Execution

**File**: `tests/test_integration.py`

**Tests**:
- ✅ Task succeeds on first attempt
- ✅ Task retries on HTTP error
- ✅ Task retries on timeout
- ✅ Job timeout protection
- ✅ Retry strategy configuration
- ✅ Exception filtering

**Run**:
```bash
pytest tests/test_integration.py -v
```

### 3. Stress Tests - Exponential Backoff

**File**: `scripts/stress_test_exponential_backoff.py`

**Tests**:
1. **Exponential Backoff Unit Test** - Verify delay calculation
2. **Max Delay Cap** - Ensure delays are capped
3. **Exception Filtering** - Test exception-specific retries
4. **Max Attempts Enforcement** - Verify retry limits
5. **Concurrent Retry Stress Test** - Test under concurrent load
6. **Different Base Delays** - Test various configurations
7. **Performance Benchmark** - Measure calculation speed

**Run**:
```bash
python scripts/stress_test_exponential_backoff.py
```

**Example Output**:
```
================================================================================
EXPONENTIAL BACKOFF STRESS TEST SUITE
================================================================================
Started at: 2024-10-14 20:45:00

================================================================================
TEST 1: Exponential Backoff Unit Test
================================================================================

Testing delay calculation:
  Attempt 1: 2s
  Attempt 2: 4s
  Attempt 3: 8s
  Attempt 4: 16s
  Attempt 5: 32s

✅ PASSED: Delays match expected exponential pattern [2, 4, 8, 16, 32]

...

================================================================================
FINAL SUMMARY
================================================================================
✅ PASSED: Exponential Backoff Unit Test
✅ PASSED: Max Delay Cap
✅ PASSED: Exception Filtering
✅ PASSED: Max Attempts Enforcement
✅ PASSED: Concurrent Retry Stress Test
✅ PASSED: Different Base Delays
✅ PASSED: Performance Benchmark

Total: 7/7 tests passed

🎉 ALL TESTS PASSED! Exponential backoff is working correctly.
```

### 4. Stress Tests - System-Wide

**File**: `scripts/stress_test_system.py`

**Tests**:
1. **Concurrent Task Submissions** - Submit 100+ tasks simultaneously
2. **Retry Behavior Under Load** - Test retries with failures
3. **Worker Capacity** - Test worker concurrency limits
4. **Burst Load Pattern** - Simulate traffic spikes
5. **Job Timeout Protection** - Verify timeout handling
6. **Database Connection Pool** - Test connection pooling
7. **Memory Usage** - Monitor memory under load
8. **Error Handling** - Test various error scenarios

**Run**:
```bash
# Full stress test
python scripts/stress_test_system.py --tasks 100

# Quick test (fewer tasks)
python scripts/stress_test_system.py --quick

# Custom number of tasks
python scripts/stress_test_system.py --tasks 500
```

**Example Output**:
```
================================================================================
SYSTEM STRESS TEST SUITE
================================================================================
Started at: 2024-10-14 20:50:00

Configuration:
  Max Retries: 5
  Base Delay: 2.0s
  Max Delay: 300.0s
  Job Timeout: 300s
  Worker Concurrency: 10

================================================================================
STRESS TEST 1: Concurrent Task Submissions (100 tasks)
================================================================================

Submitting 100 tasks concurrently...

Submission Results:
  Time taken: 2.34s
  Throughput: 42.74 submissions/sec
  Successful: 100/100
  Failed: 0/100

✅ PASSED: All tasks submitted successfully

...

================================================================================
FINAL SUMMARY
================================================================================
✅ PASSED: Concurrent Task Submissions
✅ PASSED: Retry Behavior Under Load
✅ PASSED: Worker Capacity
✅ PASSED: Burst Load Pattern
✅ PASSED: Job Timeout Protection
✅ PASSED: Database Connection Pool
✅ PASSED: Memory Usage
✅ PASSED: Error Handling

Total: 8/8 tests passed
Completed at: 2024-10-14 20:52:15

🎉 ALL STRESS TESTS PASSED! System is robust and reliable.
```

## 🎯 Test Scenarios

### Scenario 1: Verify Exponential Backoff Pattern

**Objective**: Confirm delays follow 2^n pattern

**Steps**:
```bash
python scripts/stress_test_exponential_backoff.py
```

**Expected**: Delays are 2s, 4s, 8s, 16s, 32s

**Verification**:
```python
# In test output, look for:
Attempt 1: 2s
Attempt 2: 4s
Attempt 3: 8s
Attempt 4: 16s
Attempt 5: 32s
```

### Scenario 2: Test Retry on API Failure

**Objective**: Verify tasks retry when API fails

**Steps**:
1. Edit `.env` to break API:
   ```bash
   API_BASE_URL=https://invalid-api-url.com
   ```

2. Submit a task:
   ```bash
   curl -X POST http://localhost:8000/tasks/fetch-joke
   ```

3. Watch logs for retry attempts:
   ```bash
   # You should see:
   Job 1: Fetching joke (attempt 1/5)
   Job 1: HTTP error on attempt 1
   # Wait 2 seconds
   Job 1: Fetching joke (attempt 2/5)
   Job 1: HTTP error on attempt 2
   # Wait 4 seconds
   Job 1: Fetching joke (attempt 3/5)
   ...
   ```

4. Restore API URL:
   ```bash
   API_BASE_URL=https://api.chucknorris.io
   ```

**Expected**: Task retries with exponentially increasing delays

### Scenario 3: Test Job Timeout

**Objective**: Verify jobs timeout after configured duration

**Steps**:
1. Temporarily reduce timeout in `.env`:
   ```bash
   JOB_TIMEOUT=5  # 5 seconds
   ```

2. Restart application

3. Submit task and observe timeout

**Expected**: Task times out after 5 seconds and retries

### Scenario 4: Test Stalled Job Recovery

**Objective**: Verify stalled jobs are automatically retried

**Steps**:
1. Start application:
   ```bash
   uvicorn app.main:app --reload
   ```

2. Submit multiple tasks:
   ```bash
   for i in {1..10}; do
       curl -X POST http://localhost:8000/tasks/fetch-joke
   done
   ```

3. Kill application while jobs are running:
   ```bash
   # Press Ctrl+C
   ```

4. Wait 10 minutes (or adjust cron for testing)

5. Restart application:
   ```bash
   uvicorn app.main:app --reload
   ```

6. Check logs for stalled job detection:
   ```bash
   # You should see:
   Checking for stalled jobs at timestamp...
   Found N stalled jobs, retrying...
   Successfully retried stalled job X
   ```

**Expected**: All stalled jobs are detected and retried

### Scenario 5: Test Concurrent Load

**Objective**: Verify system handles concurrent submissions

**Steps**:
```bash
python scripts/stress_test_system.py --tasks 100
```

**Expected**: All 100 tasks submitted successfully with no errors

### Scenario 6: Test Max Delay Cap

**Objective**: Verify delays don't exceed max_delay

**Steps**:
1. Configure strategy with low max_delay:
   ```python
   strategy = ExponentialBackoffStrategy(
       max_attempts=10,
       base_delay=2.0,
       max_delay=60.0,  # Cap at 60 seconds
   )
   ```

2. Run test:
   ```bash
   pytest tests/test_exponential_backoff.py::TestExponentialBackoffStrategy::test_max_delay_cap -v
   ```

**Expected**: Delays are capped at 60 seconds even for high attempt numbers

## 📈 Performance Benchmarks

### Retry Strategy Calculation Performance

**Test**: Calculate delays 100,000 times

**Expected Performance**:
- Per calculation: < 10µs
- Calculations/sec: > 100,000

**Run**:
```bash
python scripts/stress_test_exponential_backoff.py
# Look for TEST 7: Performance Benchmark
```

### Task Submission Throughput

**Test**: Submit 100 tasks concurrently

**Expected Performance**:
- Throughput: > 40 submissions/sec
- Success rate: 100%

**Run**:
```bash
python scripts/stress_test_system.py --tasks 100
# Look for STRESS TEST 1: Concurrent Task Submissions
```

## 🐛 Debugging Failed Tests

### Test Fails: Exponential Pattern Not Matched

**Symptom**: Delays don't follow 2^n pattern

**Debug**:
```python
# Check ExponentialBackoffStrategy.get_schedule_in()
# Verify formula: delay = base_delay * (2 ** attempts)
```

**Fix**: Ensure formula uses `2 ** attempts`, not `2 * attempts`

### Test Fails: Max Attempts Not Enforced

**Symptom**: Retries continue beyond max_attempts

**Debug**:
```python
# Check get_schedule_in() method
# Verify: if attempts >= self.max_attempts: return None
```

**Fix**: Ensure proper comparison with `>=`, not `>`

### Test Fails: Exception Filtering Not Working

**Symptom**: Wrong exceptions trigger/don't trigger retries

**Debug**:
```python
# Check exception filtering logic
# Verify isinstance() check for exception types
```

**Fix**: Ensure `isinstance(exception, exc_type)` is used correctly

### Test Fails: Database Connection Issues

**Symptom**: Integration tests fail with connection errors

**Debug**:
```bash
# Check PostgreSQL is running
docker-compose ps

# Check connection string
echo $DATABASE_URL
```

**Fix**: Ensure PostgreSQL is running and connection string is correct

## 📊 Coverage Report

Generate coverage report:

```bash
# Run tests with coverage
pytest tests/ --cov=app --cov-report=html --cov-report=term

# Open HTML report
open htmlcov/index.html
```

**Target Coverage**: > 80% for critical components

**Critical Components**:
- `app/procrastinate_app.py` - ExponentialBackoffStrategy
- `app/tasks.py` - Task definitions and retry logic
- `app/config.py` - Configuration management

## 🔍 Monitoring Test Results

### View Test Logs

```bash
# Run with verbose output
pytest tests/ -v -s

# Run with detailed logging
pytest tests/ --log-cli-level=INFO
```

### Continuous Integration

Add to CI/CD pipeline:

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements-test.txt
      - name: Run unit tests
        run: pytest tests/ -v --cov=app
      - name: Run stress tests
        run: |
          python scripts/stress_test_exponential_backoff.py
          python scripts/stress_test_system.py --quick
```

## ✅ Test Checklist

Before deploying to production:

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Exponential backoff stress test passes
- [ ] System stress test passes
- [ ] Manual retry scenario tested
- [ ] Stalled job recovery tested
- [ ] Job timeout protection tested
- [ ] Concurrent load tested
- [ ] Memory usage verified
- [ ] Coverage > 80%

## 🎓 Best Practices

1. **Run tests before committing**
   ```bash
   pytest tests/ -v
   ```

2. **Test retry behavior manually**
   - Break API temporarily
   - Observe exponential delays in logs
   - Verify task eventually succeeds

3. **Monitor production metrics**
   - Track retry rates
   - Monitor job completion times
   - Alert on high failure rates

4. **Regular stress testing**
   - Run weekly stress tests
   - Test with production-like load
   - Verify performance doesn't degrade

5. **Keep tests updated**
   - Add tests for new features
   - Update tests when changing retry logic
   - Maintain test documentation

## 📚 Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Procrastinate Testing Guide](https://procrastinate.readthedocs.io/en/stable/howto/django/tests.html)
- [Exponential Backoff Pattern](https://en.wikipedia.org/wiki/Exponential_backoff)

## 🆘 Getting Help

If tests fail or you need assistance:

1. Check test output for specific error messages
2. Review logs for detailed information
3. Verify configuration in `.env`
4. Ensure PostgreSQL is running
5. Check worker is processing jobs

## 🎉 Success Criteria

Tests are successful when:

- ✅ All unit tests pass (100%)
- ✅ All stress tests pass (100%)
- ✅ Exponential pattern verified
- ✅ Max delay cap enforced
- ✅ Exception filtering works
- ✅ Concurrent load handled
- ✅ No memory leaks detected
- ✅ Performance meets benchmarks

**Result**: Bulletproof task execution with verified exponential backoff! 🚀
